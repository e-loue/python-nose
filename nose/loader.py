"""
Test Loader
-----------

nose's test loader implements the same basic functionality as its
superclass, unittest.TestLoader, but extends it by more liberal
interpretations of what may be a test and how a test may be named.
"""
from __future__ import generators

import logging
import os
import sys
import unittest
from inspect import isfunction, ismethod
from nose.case import Failure, FunctionTestCase, MethodTestCase
from nose.config import Config
from nose.importer import Importer, add_path, remove_path
from nose.selector import defaultSelector, TestAddress
from nose.util import cmp_lineno, getpackage, isclass, isgenerator, ispackage, \
    match_last, resolve_name
from suite import ContextSuiteFactory, ContextList, LazySuite

log = logging.getLogger(__name__)
#log.setLevel(logging.DEBUG)

class TestLoader(unittest.TestLoader):
    """Test loader that extends unittest.TestLoader to:

    * Load tests from test-like functions and classes that are not
      unittest.TestCase subclasses
    * Find and load test modules in a directory
    * Support tests that are generators
    * Support easy extensions of or changes to that behavior through plugins
    """
    def __init__(self, config=None, importer=None, workingDir=None,
                 selector=None):
        """Initialize a test loader.

        Parameters (all optional):

        * config: provide a `nose.config.Config` or other config class
          instance; if not provided a `nose.config.Config` with
          default values is used.          
        * importer: provide an importer instance that implenents
          `importFromPath`. If not provided, a
          `nose.importer.Importer` is used.
        * workingDir: the directory to which file and module names are
          relative. If not provided, assumed to be the current working
          directory.
        * selector: a selector class. If not provided, a
          `nose.selector.Selector1 is used.
        """
        # FIXME would get selector too
        if config is None:
            config = Config()
        if importer is None:
            importer = Importer(config=config)
        if workingDir is None:
            workingDir = os.getcwd()
        if selector is None:
            selector = defaultSelector(config)
        self.config = config
        self.importer = importer
        self.workingDir = os.path.normpath(os.path.abspath(workingDir))
        self.selector = selector
        if config.addPaths:
            add_path(workingDir, config)        
        self.suiteClass = ContextSuiteFactory(config=config)
        unittest.TestLoader.__init__(self)        

    def getTestCaseNames(self, testCaseClass):
        """Override to select with selector, unless
        config.getTestCaseNames.Compat is True
        """
        if self.config.getTestCaseNamesCompat:
            return unittest.TestLoader.getTestCaseNames(self, testCaseClass)
        
        def wanted(attr, cls=testCaseClass, sel=self.selector):
            item = getattr(cls, attr, None)
            if not ismethod(item):
                return False
            return sel.wantMethod(item)
        cases = filter(wanted, dir(testCaseClass))
        for base in testCaseClass.__bases__:
            for case in self.getTestCaseNames(base):
                if case not in cases:
                    cases.append(case)
        # add runTest if nothing else picked
        if not cases and hasattr(testCaseClass, 'runTest'):
            cases = ['runTest']
        if self.sortTestMethodsUsing:
            cases.sort(self.sortTestMethodsUsing)
        return cases

    def loadTestsFromDir(self, path):
        """Load tests from the directory at path. This is a generator
        -- each suite of tests from a module or other file is yielded
        and is expected to be executed before the next file is
        examined.
        """        
        log.debug("load from dir %s", path)
        plugins = self.config.plugins
        plugins.beforeDirectory(path)
        if self.config.addPaths:
            paths_added = add_path(path, self.config)

        entries = os.listdir(path)
        entries.sort(lambda a, b: match_last(a, b, self.config.testMatch))
        for entry in entries:
            if entry.startswith('.') or entry.startswith('_'):
                continue
            entry_path = os.path.abspath(os.path.join(path, entry))
            is_file = os.path.isfile(entry_path)
            is_test = False
            if is_file:
                is_dir = False
                is_test = self.selector.wantFile(entry_path)
            else:
                is_dir = os.path.isdir(entry_path)
                if is_dir:
                    is_test = self.selector.wantDirectory(entry_path)
            is_package = ispackage(entry_path)
            if is_test and is_file:
                plugins.beforeContext()
                if entry.endswith('.py'):
                    yield self.loadTestsFromName(
                        entry_path, discovered=True)
                else:
                    yield self.loadTestsFromFile(entry_path)
                plugins.afterContext()
            elif is_dir:
                if is_package:
                    # Load the entry as a package: given the full path,
                    # loadTestsFromName() will figure it out
                    yield self.loadTestsFromName(
                        entry_path, discovered=True)
                elif is_test:
                    # Another test dir in this one: recurse lazily
                    yield self.suiteClass(
                        lambda: self.loadTestsFromDir(entry_path))
        # give plugins a chance
        try:
            tests = []
            for test in plugins.loadTestsFromDir(path):
                tests.append(test)
            yield self.suiteClass(tests)
        except (TypeError, AttributeError):
            pass
        # pop paths
        if self.config.addPaths:
            map(remove_path, paths_added)
        plugins.afterDirectory(path)

    def loadTestsFromFile(self, filename):
        """Load tests from a non-module file. Default is to raise a
        ValueError; plugins may implement `loadTestsFromFile` to
        provide a list of tests loaded from the file.
        """
        log.debug("Load from non-module file %s", filename)
        try:
            tests = [test for test in
                     self.config.plugins.loadTestsFromFile(filename)]
            if tests:
                # Plugins can yield False to indicate that they were
                # unable to load tests from a file, but it was not an
                # error -- the file just had no tests to load.
                tests = filter(None, tests)
                return self.suiteClass(tests)
            else:
                # Nothing was able to even try to load from this file
                open(filename, 'r').close() # trigger os error
                raise ValueError("Unable to load tests from file %s"
                                 % filename)
        except KeyboardInterrupt:
            raise
        except:
            exc = sys.exc_info()
            return self.suiteClass([Failure(*exc)])

    def loadTestsFromGenerator(self, generator, module):
        """Lazy-load tests from a generator function. The generator function
        may yield either:

        * a callable, or
        * a function name resolvable within the same module
        """
        def generate(g=generator, m=module):
            for test in g():
                try:
                    test_func, arg = (test[0], test[1:])
                except ValueError:
                    test_func, arg = test[0], tuple()
                if not callable(test_func):
                    test_func = getattr(m, test_func)
                yield FunctionTestCase(test_func, arg=arg, descriptor=g)
        return self.suiteClass(generate)

    def loadTestsFromGeneratorMethod(self, generator, cls):
        """Lazy-load tests from a generator method.

        This is more complicated than loading from a generator function,
        since a generator method may yield:

        * a function
        * a bound or unbound method, or
        * a method name
        """
        # convert the unbound generator method
        # into a bound method so it can be called below
        cls = generator.im_class
        inst = cls()
        method = generator.__name__
        generator = getattr(inst, method)

        def generate(g=generator, c=cls):
            for test in g():
                try:
                    test_func, arg = (test[0], test[1:])
                except ValueError:
                    test_func, arg = test[0], tuple()
                if not callable(test_func):
                    test_func = getattr(c, test_func)
                if ismethod(test_func):
                    yield MethodTestCase(test_func, arg=arg, descriptor=g)
                elif isfunction(test_func):
                    # In this case we're forcing the 'MethodTestCase'
                    # to run the inline function as its test call,
                    # but using the generator method as the 'method of
                    # record' (so no need to pass it as the descriptor)
                    yield MethodTestCase(g, test=test_func, arg=arg)
                else:
                    yield Failure(TypeError,
                                  "%s is not a function or method" % test_func)
        return self.suiteClass(generate)

    def loadTestsFromModule(self, module, discovered=False):
        """Load all tests from module and return a suite containing
        them. If the module has been discovered and is not test-like,
        the suite will be empty by default, though plugins may add
        their own tests.
        """
        log.debug("Load from module %s", module)
        tests = []
        test_classes = []
        test_funcs = []
        # For *discovered* modules, we only load tests when the module looks
        # testlike. For modules we've been directed to load, we always
        # look for tests. (discovered is set to True by loadTestsFromDir)
        if not discovered or self.selector.wantModule(module):
            for item in dir(module):
                test = getattr(module, item, None)
                # print "Check %s (%s) in %s" % (item, test, module.__name__)
                if isclass(test):
                    if self.selector.wantClass(test):
                        test_classes.append(test)
                elif isfunction(test) and self.selector.wantFunction(test):
                    test_funcs.append(test)
            test_classes.sort(lambda a, b: cmp(a.__name__, b.__name__))
            test_funcs.sort(cmp_lineno)
            tests = map(lambda t: self.makeTest(t, parent=module),
                        test_classes + test_funcs)

        # Now, descend into packages
        # FIXME can or should this be lazy?
        # is this syntax 2.3 (or 2.2) compatible?
        paths = getattr(module, '__path__', [])
        for path in paths:
            tests.extend(self.loadTestsFromDir(path))
            
        # give plugins a chance
        try:
            for test in self.config.plugins.loadTestsFromModule(module):
                tests.append(test)
        except (TypeError, AttributeError):
            pass

        return self.suiteClass(ContextList(tests, context=module))
    
    def loadTestsFromName(self, name, module=None, discovered=False):
        """Load tests from the entity with the given name.

        The name may indicate a file, directory, module, or any object
        within a module. See `nose.util.split_test_name` for details on
        test name parsing.
        """
        # FIXME refactor this method into little bites?
        log.debug("load from %s (%s)", name, module)
        
        suite = self.suiteClass

        # give plugins first crack
        plug_tests = self.config.plugins.loadTestsFromName(name, module)
        if plug_tests:
            return suite(plug_tests)
        
        addr = TestAddress(name, workingDir=self.workingDir)
        if module:
            # Two cases:
            #  name is class.foo
            #    The addr will be incorrect, since it thinks class.foo is
            #    a dotted module name. It's actually a dotted attribute
            #    name. In this case we want to use the full submitted
            #    name as the name to load from the module.
            #  name is module:class.foo
            #    The addr will be correct. The part we want is the part after
            #    the :, which is in addr.call.
            if addr.call:
                name = addr.call
            parent, obj = self.resolve(name, module)
            return suite(ContextList([self.makeTest(obj, parent)],
                                     context=parent))
        else:
            if addr.module:
                try:
                    if addr.filename is None:
                        module = resolve_name(addr.module)
                    else:
                        self.config.plugins.beforeImport(
                            addr.filename, addr.module)
                        # FIXME: to support module.name names,
                        # do what resolve-name does and keep trying to
                        # import, popping tail of module into addr.call,
                        # until we either get an import or run out of
                        # module parts
                        try:
                            module = self.importer.importFromPath(
                                addr.filename, addr.module)
                        finally:
                            self.config.plugins.afterImport(
                                addr.filename, addr.module)
                except KeyboardInterrupt, SystemExit:
                    raise
                except:
                    exc = sys.exc_info()
                    return suite([Failure(*exc)])
                if addr.call:
                    return self.loadTestsFromName(addr.call, module)
                else:
                    return self.loadTestsFromModule(
                        module, discovered=discovered)
            elif addr.filename:
                path = addr.filename
                if addr.call:
                    package = getpackage(path)
                    if package is None:
                        return suite([
                            Failure(ValueError,
                                    "Can't find callable %s in file %s: "
                                    "file is not a python module" %
                                    (addr.call, path))])
                    return self.loadTestsFromName(addr.call, module=package)
                else:
                    if os.path.isdir(path):
                        # In this case we *can* be lazy since we know
                        # that each module in the dir will be fully
                        # loaded before its tests are executed; we
                        # also know that we're not going to be asked
                        # to load from . and ./some_module.py *as part
                        # of this named test load*
                        return LazySuite(
                            lambda: self.loadTestsFromDir(path))
                    elif os.path.isfile(path):
                        return self.loadTestsFromFile(path)
                    else:
                        return suite([
                                Failure(OSError, "No such file %s" % path)])
            else:
                # just a function? what to do? I think it can only be
                # handled when module is not None
                return suite([
                    Failure(ValueError, "Unresolvable test name %s" % name)])

    def loadTestsFromNames(self, names, module=None):
        """Load tests from all names, returning a suite containing all
        tests.
        """
        plug_res = self.config.plugins.loadTestsFromNames(names, module)
        if plug_res:
            suite, names = plug_res
            if suite:
                return self.suiteClass([
                    self.suiteClass(suite),
                    unittest.TestLoader.loadTestsFromNames(self, names, module)
                    ])
        return unittest.TestLoader.loadTestsFromNames(self, names, module)

#    def loadTestsFromTestCase(self, testCaseClass):
#        names = self.getTestCaseNames(testCaseClass)
        
    
    def loadTestsFromTestClass(self, cls):
        """Load tests from a test class that is *not* a unittest.TestCase
        subclass.

        In this case, we can't depend on the class's `__init__` taking method
        name arguments, so we have to compose a MethodTestCase for each
        method in the class that looks testlike.        
        """
        def wanted(attr, cls=cls, sel=self.selector):
            item = getattr(cls, attr, None)
            if not ismethod(item):
                return False
            return sel.wantMethod(item)
        cases = [self.makeTest(getattr(cls, case), cls)
                 for case in filter(wanted, dir(cls))]
        # Give plugins a chance
        try:
            for test in self.config.plugins.loadTestsFromTestClass(cls):
                cases.append(test)
        except (TypeError, AttributeError):
            pass
        return self.suiteClass(ContextList(cases, context=cls))

    def makeTest(self, obj, parent=None):
        """Given a test object and its parent, return a test case
        or test suite.
        """
        # plugins get first crack
        plug_tests = []
        try:
            for test in self.config.plugins.makeTest(obj, parent):
                plug_tests.append(test)
            if plug_tests:
                return self.suiteClass(plug_tests)
        except (TypeError, AttributeError):
            pass
        if isinstance(obj, unittest.TestCase):
            return obj
        elif isclass(obj):            
            if issubclass(obj, unittest.TestCase):
                return self.loadTestsFromTestCase(obj)
            else:
                return self.loadTestsFromTestClass(obj)
        elif ismethod(obj):
            if parent is None:
                parent = obj.__class__
            if issubclass(parent, unittest.TestCase):
                return parent(obj.__name__)
            else:
                if isgenerator(obj):
                    return self.loadTestsFromGeneratorMethod(obj, parent)
                else:
                    return MethodTestCase(obj)
        elif isfunction(obj):
            if isgenerator(obj):
                return self.loadTestsFromGenerator(obj, parent)
            else:
                return FunctionTestCase(obj)
        else:
            return Failure(TypeError,
                           "Can't make a test from %s" % obj)

    def resolve(self, name, module):
        """Resolve name within module
        """
        obj = module
        parts = name.split('.')
        for part in parts:
            parent, obj = obj, getattr(obj, part, None)
        if obj is None:
            # no such test
            obj = Failure(ValueError, "No such test %s" % name)
        return parent, obj

defaultTestLoader = TestLoader

