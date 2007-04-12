"""nose plugins

nose supports setuptools entry point plugins for test collection,
selection, observation and reporting.

Writing Plugins
---------------

Plugin classes should subclass nose.plugins.Plugin.

Plugins may implement any of the methods described in the class
PluginInterface in nose.plugins.base. Please note that this class is for
documentary purposes only; plugins may not subclass PluginInterface.

Registering
===========

For nose to find a plugin, it must be part of a package that uses
setuptools, and the plugin must be included in the entry points defined
in the setup.py for the package::

  setup(name='Some plugin',
        ...
        entry_points = {
            'nose.plugins': [
                'someplugin = someplugin:SomePlugin'
                ]
            },
        ...
        )

Once the package is installed with install or develop, nose will be able
to load the plugin.

Defining options
================

All plugins must implement the methods `add_options(self, parser, env)`
and `configure(self, options, conf)`. Subclasses of nose.plugins.Plugin
that want the standard options should call the superclass methods.

nose uses optparse.OptionParser from the standard library to parse
arguments. A plugin's add_options() method receives a parser
instance. It's good form for a plugin to use that instance only to add
additional arguments that take only long arguments (--like-this). Most
of nose's built-in arguments get their default value from an environment
variable. This is a good practice because it allows options to be
utilized when run through some other means than the nosetests script.

A plugin's configure() receives the parsed OptionParser options object,
as well as the current config object. Plugins should configure their
behavior based on the user-selected settings, and may raise exceptions
if the configured behavior is nonsensical.

Logging
=======

nose uses the logging classes from the standard library. To enable users
to view debug messages easily, plugins should use logging.getLogger() to
acquire a logger in the 'nose.plugins' namespace.

Recipes
=======

 * Writing a plugin that monitors or controls test result output

   Implement any or all of addError, addFailure, etc., to monitor test
   results. If you also want to monitor output, implement
   setOutputStream and keep a reference to the output stream. If you
   want to prevent the builtin TextTestResult output, implement
   setOutputSteam and return a dummy stream and send your desired output
   to the real stream.
 
   Example: examples/html_plugin/htmlplug.py

 * Writing a plugin that loads tests from files other than python modules

   Implement wantFile and loadTestsFromPath. In wantFile, return True
   for files that you want to examine for tests. In loadTestsFromPath,
   for those files, return a TestSuite or other iterable containing
   TestCases. loadTestsFromPath may also be a generator.
 
   Example: nose.plugins.doctests

 * Writing a plugin that prints a report

   Implement begin if you need to perform setup before testing
   begins. Implement report and output your report to the provided stream.
 
   Examples: nose.plugins.cover, nose.plugins.profile, nose.plugins.missed

 * Writing a plugin that selects or rejects tests

   Implement any or all want* methods. Return False to reject the test
   candidate, True to accept it -- which  means that the test candidate
   will pass through the rest of the system, so you must be prepared to
   load tests from it if tests can't be loaded by the core loader or
   another plugin -- and None if you don't care.

   Examples: nose.plugins.attrib, nose.plugins.doctests
   
Examples
========

See nose.plugins.attrib, nose.plugins.cover, nose.plugins.doctests and
nose.plugins.profile for examples. Further examples may be found the
examples directory in the nose source distribution.

Testing Plugins
===============

The plugin interface is well-tested enough so that you can safely unit
test your use of its hooks with some level of confidence.  However,
there is a mixin for unittest.TestCase called PluginTester that's
designed to test plugins in their native runtime environment.

Here's a simple example with a do-nothing plugin and a composed suite.

    >>> import unittest
    >>> from nose.plugins import Plugin, PluginTester
    >>> class FooPlugin(Plugin):
    ...     pass
    >>> class TestPluginFoo(PluginTester, unittest.TestCase):
    ...     activate = '--with-foo'
    ...     debuglog = 'nose.plugins.foo'
    ...     plugins = [FooPlugin()]
    ...     def test_foo(self):
    ...         for line in self.output:
    ...             # i.e. check for patterns
    ...             pass
    ... 
    ...         # or check for a line containing ...
    ...         assert "ValueError" in self.output
    ...     def makeSuite(self):
    ...         class TC(unittest.TestCase):
    ...             def runTest(self):
    ...                 raise ValueError("I hate foo")
    ...         return unittest.TestSuite([TC()])
    ...
    >>> res = unittest.TestResult()
    >>> case = TestPluginFoo('test_foo')
    >>> case(res)
    >>> res.errors
    []
    >>> res.failures
    []
    >>> res.wasSuccessful()
    True
    >>> res.testsRun
    1
"""
from nose.plugins.base import Plugin
from nose.plugins.manager import *
from nose.plugins.plugintest import PluginTester



