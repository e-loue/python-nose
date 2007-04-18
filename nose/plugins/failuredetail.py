import os
from nose.plugins import Plugin
from nose.inspector import inspect_traceback

class FailureDetail(Plugin):
    score = 600 # before capture
    
    def options(self, parser, env=os.environ):
        parser.add_option(
            "-d", "--detailed-errors", "--failure-detail",
            action="store_true",
            default=env.get('NOSE_DETAILED_ERRORS'),
            dest="detailedErrors", help="Add detail to error"
            " output by attempting to evaluate failed"
            " asserts [NOSE_DETAILED_ERRORS]")

    def configure(self, options, conf):
        if not self.can_configure:
            return
        self.enabled = options.detailedErrors
        self.conf = conf

    def formatFailure(self, test, err):
        """Add detail from traceback inspection to error message of a failure.
        """
        ec, ev, tb = err
        tbinfo = inspect_traceback(tb)
        test.tbinfo = tbinfo
        ev = '\n'.join([str(ev), tbinfo])
        return (ec, ev, tb)
