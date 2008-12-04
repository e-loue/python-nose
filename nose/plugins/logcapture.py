"""
This plugin captures logging statements issued during test
execution, appending any output captured to the error or failure
output, should the test fail or raise an error. It is enabled by
default but may be disabled with the options --nologcapture.

To remove any other installed logging handlers, use the
--logging-clear-handlers option.

When an error or failure occurs, captures log messages are attached to
the running test in the test.capturedLogging attribute, and added to
the error failure output.

You can filter logging statements captured with the --logging-filter option. 
If set, it specifies which logger(s) will be captured; loggers that do not match
will be passed. Example: specifying --logging-filter=sqlalchemy,myapp 
will ensure that only statements logged via sqlalchemy.engine or myapp
or myapp.foo.bar logger will be logged.
"""

import os
import logging
from logging.handlers import BufferingHandler

from nose.plugins.base import Plugin
from nose.util import ln

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

log = logging.getLogger(__name__)


class MyMemoryHandler(BufferingHandler):
    def __init__(self, capacity, logformat, filters):
        BufferingHandler.__init__(self, capacity)
        fmt = logging.Formatter(logformat)
        self.setFormatter(fmt)
        self.filters = filters
    def flush(self):
        pass # do nothing
    def truncate(self):
        self.buffer = []
    def filter(self, record):
        """Our custom record filtering logic.

        Built-in filtering logic (via logging.Filter) is too limiting.
        """
        if not self.filters:
            return True
        matched = False
        rname = record.name # shortcut
        for name in self.filters:
            if rname == name or rname.startswith(name+'.'):
                matched = True
        return matched


class LogCapture(Plugin):
    """
    Log capture plugin. Enabled by default. Disable with --nologcapture.
    This plugin captures logging statement issued during test execution,
    appending any output captured to the error or failure output,
    should the test fail or raise an error.    
    """
    enabled = True
    env_opt = 'NOSE_NOLOGCAPTURE'
    name = 'logcapture'
    score = 500
    logformat = '%(name)s: %(levelname)s: %(message)s'
    clear = False
    filters = []
    
    def options(self, parser, env=os.environ):
        parser.add_option(
            "", "--nologcapture", action="store_false",
            default=not env.get(self.env_opt), dest="logcapture",
            help="Disable logging capture plugin. "
                 "Logging configurtion will be left intact."
                 " [NOSE_NOLOGCAPTURE]")
        parser.add_option(
            "", "--logging-format", action="store", dest="logcapture_format",
            default=env.get('NOSE_LOGFORMAT') or self.logformat,
            help="Specify custom format to print statements. "
                 "Uses the same format as used by standard logging handlers."
                 " [NOSE_LOGFORMAT]")
        parser.add_option(
            "", "--logging-filter", action="store", dest="logcapture_filters",
            default=env.get('NOSE_LOGFILTER'),
            help="Specify which statements to filter in/out. "
                 "By default everything is captured. If the output is too"
                 " verbose,\nuse this option to filter out needless output\n"
                 "Example: filter=foo will capture statements issued ONLY to\n"
                 " foo or foo.what.ever.sub but not foobar or other logger.\n"
                 "Specify multiple loggers with comma: filter=foo,bar,baz."
                 " [NOSE_LOGFILTER]\n")
        parser.add_option(
            "", "--logging-clear-handlers", action="store_true",
            default=False, dest="logcapture_clear",
            help="Clear all other logging handlers")

    def configure(self, options, conf):
        self.conf = conf
        # Disable if explicitly disabled, or if logging is
        # configured via logging config file
        if not options.logcapture or conf.loggingConfig:
            self.enabled = False        
        self.logformat = options.logcapture_format
        self.clear = options.logcapture_clear
        if options.logcapture_filters:
            self.filters = options.logcapture_filters.split(',')
        
    def setupLoghandler(self):
        # setup our handler with root logger
        root_logger = logging.getLogger()
        if self.clear:
            for handler in root_logger.handlers:
                root_logger.removeHandler(handler)
        # make sure there isn't one already
        # you can't simply use "if self.handler not in root_logger.handlers"
        # since at least in unit tests this doesn't work --
        # LogCapture() is instantiated for each test case while root_logger
        # is module global
        # so we always add new MyMemoryHandler instance
        for handler in root_logger.handlers[:]:
            if isinstance(handler, MyMemoryHandler):
                root_logger.handlers.remove(handler)
        root_logger.addHandler(self.handler)
        # to make sure everything gets captured
        root_logger.setLevel(logging.NOTSET)

    def begin(self):
        self.start()

    def start(self):
        self.handler = MyMemoryHandler(1000, self.logformat, self.filters)
        self.setupLoghandler()

    def end(self):
        pass

    def beforeTest(self, test):
        self.setupLoghandler()

    def afterTest(self, test):
        self.handler.truncate()

    def formatFailure(self, test, err):
        return self.formatError(test, err)

    def formatError(self, test, err):
        # logic flow copied from Capture.formatError
        test.capturedLogging = records = self.formatLogRecords()
        if not records:
            return err 
        ec, ev, tb = err
        return (ec, self.addCaptureToErr(ev, records), tb)

    def formatLogRecords(self):
        format = self.handler.format
        return [format(r) for r in self.handler.buffer]

    def addCaptureToErr(self, ev, records):
        return '\n'.join([str(ev), ln('>> begin captured logging <<')] + \
                          records + \
                          [ln('>> end captured logging <<')])
