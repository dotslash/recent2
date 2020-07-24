import io
import os
import time
import unittest
import unittest.mock as mock

import recent2


class tests_option:
    untested_options = set(action.dest for action in recent2.make_arg_parser_for_recent()._actions)
    _valid_options = set(action.dest for action in recent2.make_arg_parser_for_recent()._actions)

    def __init__(self, option):
        assert option in tests_option._valid_options
        tests_option.untested_options.discard(option)

    def __call__(self, f):
        def wrapped_f(*args):
            f(*args)

        return wrapped_f


class RecentTest(unittest.TestCase):

    def setUp(self) -> None:
        # Use an in-memory shared database for this test.
        # This will automatically be destroyed after the last connection is closed
        # https://www.sqlite.org/inmemorydb.html
        IN_MEM_DB = 'file::memory:?cache=shared'
        os.environ['RECENT_DB'] = IN_MEM_DB
        os.environ['PROMPT_COMMAND'] = recent2.EXPECTED_PROMPT

        self._arg_parser = recent2.make_arg_parser_for_recent()
        self._shell_pid = int(time.time())
        self._sequence = 0
        self._time_secs = time.time()

        # Initialize the session
        self._keep_alive_conn = recent2.create_connection()
        session = recent2.Session(self._shell_pid, self._sequence)
        session.update(self._keep_alive_conn)
        # Do not close the connection. Keep it alive to make sure the in mem db is not cleaned up
        self._keep_alive_conn.commit()

    def tearDown(self) -> None:
        self._keep_alive_conn.close()

    @classmethod
    def tearDownClass(cls) -> None:
        untested_options = {
            'help',  # Need not test help
            'debug',  # Will not test debug mode. It add misc log statements.
            # TODO: Add tests for the following options
            'sql', 're', 'd', 'columns', 'detail', 'hide_time'
        }
        assert tests_option.untested_options == untested_options

    def logCmd(self, cmd, return_value=0, pwd="/root"):
        self._sequence += 1
        self._time_secs += 1
        with mock.patch('time.time', return_value=self._time_secs):
            recent2.log_command(command=cmd, pid=self._shell_pid, sequence=self._sequence,
                                return_value=return_value, pwd=pwd)

    def query(self, query):
        args = self._arg_parser.parse_args(query.split(" "))
        with mock.patch('sys.stdout', new=io.StringIO()) as fake_out:
            recent2.handle_recent_command(args, self._arg_parser.print_help)
            out = fake_out.getvalue().strip()
            if out == '':
                return []
            return out.split("\n")

    def check_without_ts(self, result_lines, expected_lines):
        time_template = recent2.Term.WARNING + "2020-07-20 21:52:33 " + recent2.Term.ENDC
        # Strip the time prefix on the results before comparing.
        result_lines = [r[len(time_template):] for r in result_lines]
        self.assertEqual(expected_lines, result_lines)

    @tests_option("n")
    def test_tail(self):
        commands = ["command{}".format(i) for i in range(30)]
        for c in commands:
            self.logCmd(c)
        self.check_without_ts(self.query(""), commands[-20:])
        self.check_without_ts(self.query("-n 5"), commands[-5:])
        self.check_without_ts(self.query("-n 20"), commands[-20:])
        self.check_without_ts(self.query("-n 25"), commands[-25:])
        # We have only 30 items logged
        self.check_without_ts(self.query("-n 100"), commands)

    def test_tail_duplicate(self):
        # Runs test tail again. This will make sure that we are creating & cleaning up properly
        # in the tests.
        self.test_tail()

    @tests_option("return_self")
    def test_return_self(self):
        commands = ["command{}".format(i) for i in range(5)] + \
                   ["recent {}".format(i) for i in range(5)]
        for c in commands:
            self.logCmd(c)
        # By default dont return recent commands.
        self.check_without_ts(self.query(""), commands[:5])
        # Passed return_self argument => return recent commands.
        self.check_without_ts(self.query("--return_self"), commands)

    @tests_option("successes_only")
    @tests_option("failures_only")
    @tests_option("status_num")
    def test_status(self):
        self.logCmd("status0 1", return_value=0)
        self.logCmd("status0 2", return_value=0)
        self.logCmd("status1 1", return_value=1)
        self.logCmd("status1 2", return_value=1)
        self.logCmd("status2 1", return_value=2)
        self.logCmd("status2 2", return_value=2)

        success_cmds = ["status0 1", "status0 2"]
        status1_cmds = ["status1 1", "status1 2"]
        status2_cmds = ["status2 1", "status2 2"]

        # Default => all commands.
        self.check_without_ts(self.query(""), success_cmds + status1_cmds + status2_cmds)

        self.check_without_ts(self.query("--successes_only"), success_cmds)
        self.check_without_ts(self.query("-so"), success_cmds)

        self.check_without_ts(self.query("--failures_only"), status1_cmds + status2_cmds)
        self.check_without_ts(self.query("-fo"), status1_cmds + status2_cmds)

        self.check_without_ts(self.query("--status_num 1"), status1_cmds)
        self.check_without_ts(self.query("-stn 1"), status1_cmds)

    @tests_option("char_limit")
    def test_char_limit(self):
        self.logCmd("c" * 190)  # 190 chars
        self.logCmd("c" * 200)  # 200 chars
        self.logCmd("c" * 210)  # 210 chars
        # default is 200 char limit
        self.check_without_ts(self.query(""), ["c" * 190, "c" * 200])
        # Check with explicit limits
        self.check_without_ts(self.query("-cl 190"), ["c" * 190])
        self.check_without_ts(self.query("--char_limit 190"), ["c" * 190])
        self.check_without_ts(self.query("--char_limit 200"), ["c" * 190, "c" * 200])
        self.check_without_ts(self.query("--char_limit 210"), ["c" * 190, "c" * 200, "c" * 210])

    @tests_option("nocase")
    @tests_option("pattern")
    def test_case(self):
        self.logCmd("abc")
        self.logCmd("aBc")

        self.check_without_ts(self.query("abc"), ["abc"])
        self.check_without_ts(self.query("abc --nocase"), ["abc", "aBc"])
        self.check_without_ts(self.query("abc -nc"), ["abc", "aBc"])

    @tests_option("pattern")
    def test_pattern(self):
        cmds = [
            "head common 0only tail",
            "head 1only common tail",
        ]
        self.logCmd(cmds[0])
        self.logCmd(cmds[1])
        self.check_without_ts(self.query("common"), cmds)
        self.check_without_ts(self.query("0only"), [cmds[0]])
        self.check_without_ts(self.query("1only"), [cmds[1]])
        self.check_without_ts(self.query("head%tail"), cmds)
        self.check_without_ts(self.query("head%0only%tail"), [cmds[0]])
        self.check_without_ts(self.query("head%1only%tail"), [cmds[1]])

    @tests_option("w")
    def test_workdir(self):
        self.logCmd("workdir1", pwd="/home/myuser1/workdir1")
        self.logCmd("workdir2", pwd="/home/myuser2/workdir2")

        # Test using full path.
        self.check_without_ts(self.query("-w /home/myuser1/workdir1"), ["workdir1"])
        self.check_without_ts(self.query("-w /home/myuser2/workdir2"), ["workdir2"])
        # Test if relative paths work by mocking pwd
        with mock.patch('os.getcwd', return_value='/home'):
            self.check_without_ts(self.query("-w myuser1/workdir1"), ["workdir1"])
            self.check_without_ts(self.query("-w myuser2/workdir2"), ["workdir2"])
        # Test if . works as an argument.
        with mock.patch('os.getcwd', return_value='/home/myuser1/workdir1'):
            self.check_without_ts(self.query("-w ."), ["workdir1"])
        # Test if ~ works.
        os.environ["HOME"] = "/home/myuser1"
        self.check_without_ts(self.query("-w ~/workdir1"), ["workdir1"])
        os.environ["HOME"] = "/home/myuser2"
        self.check_without_ts(self.query("-w ~/workdir2"), ["workdir2"])

    @tests_option("env")
    def tests_env(self):
        os.environ['IGNORE'] = 'ignore'
        # All env vars that start with RECENT_ are captured by default.
        # The following environment vars are explicitly captured.
        os.environ['RECENT_ENV_VARS'] = 'EXPLICIT_CAPTURE,EXPLICIT_CAPTURE2'
        set1 = {'RECENT_CAPTURE': 'implicit1', 'EXPLICIT_CAPTURE': 'explicit1'}
        set2 = {'RECENT_CAPTURE': 'implicit2', 'EXPLICIT_CAPTURE': 'explicit2'}
        for s in (set1, set2):
            for k in s.keys():
                if k in os.environ:
                    del os.environ[k]

        self.logCmd("capture_none")
        os.environ.update(set1)
        self.logCmd("capture_set1")
        self.logCmd("capture_set1 again")
        os.environ.update(set2)
        self.logCmd("capture_set2")
        self.logCmd("capture_set2 again")

        # Neither implicitly captured or explicitly captured
        self.check_without_ts(self.query("--env IGNORE"), [])

        # Query by env var key.
        self.check_without_ts(self.query("--env RECENT_CAPTURE"),
                              ["capture_set1", "capture_set1 again",
                               "capture_set2", "capture_set2 again"])
        self.check_without_ts(self.query("--env EXPLICIT_CAPTURE"),
                              ["capture_set1", "capture_set1 again",
                               "capture_set2", "capture_set2 again"])
        # Query by env var value.
        self.check_without_ts(self.query("--env EXPLICIT_CAPTURE:explicit1"),
                              ["capture_set1", "capture_set1 again"])
        self.check_without_ts(self.query("--env EXPLICIT_CAPTURE:explicit2"),
                              ["capture_set2", "capture_set2 again"])

        self.check_without_ts(self.query("--env RECENT_CAPTURE:implicit1"),
                              ["capture_set1", "capture_set1 again"])
        self.check_without_ts(self.query("--env RECENT_CAPTURE:implicit2"),
                              ["capture_set2", "capture_set2 again"])


if __name__ == '__main__':
    unittest.main()
