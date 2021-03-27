from datetime import datetime, timedelta, timezone
import io
import os
import time
import unittest
import unittest.mock as mock
import uuid
from pathlib import Path

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


def currenttz():
    if time.daylight:
        return timezone(timedelta(seconds=-time.altzone), time.tzname[1])
    else:
        return timezone(timedelta(seconds=-time.timezone), time.tzname[0])


class TestBase(unittest.TestCase):
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
        self.initSession(self._shell_pid)

    def initSession(self, pid):
        session = recent2.Session(pid, 0)
        session.update(self._keep_alive_conn)
        # Do not close the connection. Keep it alive to make sure the in mem db is not cleaned up
        self._keep_alive_conn.commit()

    def tearDown(self) -> None:
        self._keep_alive_conn.close()

    def query(self, query):
        return self.query_with_args(query.split(" "))

    def query_with_args(self, args):
        args = self._arg_parser.parse_args(args)
        with mock.patch('sys.stdout', new=io.StringIO()) as fake_out:
            recent2.handle_recent_command(args, self._arg_parser.exit)
            out = fake_out.getvalue().strip()
            if out == '':
                return []
            return out.split("\n")

    def check_without_ts(self, result_lines, expected_lines):
        yellow, endc = recent2.Term.YELLOW, recent2.Term.ENDC
        time_template = f" # rtime@ {yellow}2020-07-20 21:52:33{endc}"
        # Strip the time suffix on the results before comparing.
        result_lines = [r[:-len(time_template)] for r in result_lines]
        self.assertEqual(expected_lines, result_lines)

    def check_with_ts(self, result_lines, expected_lines):
        yellow, endc = recent2.Term.YELLOW, recent2.Term.ENDC

        # Strip the time suffix on the results before comparing.
        def fmt_time(x):
            # Im not sure why timezone is being picked by recent as utc here.
            # But the cli normally returns localtime
            return datetime.fromtimestamp(x, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        expected_lines = [
            f"{cmd} # rtime@ {yellow}{fmt_time(cmd_time_secs)}{endc}"
            for cmd, cmd_time_secs in expected_lines
        ]
        self.assertEqual(expected_lines, result_lines)


class RecentTest(TestBase):
    @classmethod
    def tearDownClass(cls) -> None:
        untested_options = {
            'help',  # Need not test help
            # TODO: These options change how we display the results. Figure out how to test them.
            'columns',
            'detail',
        }
        assert tests_option.untested_options == untested_options

    def logCmd(self, cmd, return_value=0, pwd="/root", time_secs=None, shell_pid=None):
        self._sequence += 1
        self._time_secs += 1
        with mock.patch('time.time', return_value=time_secs or self._time_secs):
            recent2.log_command(command=cmd,
                                pid=shell_pid or self._shell_pid,
                                sequence=self._sequence,
                                return_value=return_value,
                                pwd=pwd)

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

    @tests_option("hide_time")
    def test_hide_time(self):
        self.logCmd("cmd1")
        self.logCmd("cmd2")
        # Time will not be printed, we can check the raw lines directly
        self.assertEqual(["cmd1", "cmd2"], self.query("--hide_time"))
        self.assertEqual(["cmd1", "cmd2"], self.query("-ht"))

    @tests_option("time_first")
    def test_time_first(self):
        def strip_time(result_lines):
            time_template = recent2.Term.YELLOW + "2020-07-20 21:52:33 " + recent2.Term.ENDC
            return [r[len(time_template):] for r in result_lines]

        self.logCmd("cmd1")
        self.logCmd("cmd2")
        self.assertEqual(["cmd1", "cmd2"], strip_time(self.query("--time_first")))
        self.assertEqual(["cmd1", "cmd2"], strip_time(self.query("-tf")))

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

        def red(x):
            return recent2.Term.FAIL + x + recent2.Term.ENDC

        success_cmds = ["status0 1", "status0 2"]
        status1_cmds = [red("status1 1"), red("status1 2")]
        status2_cmds = [red("status2 1"), red("status2 2")]

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
        self.logCmd("c" * 390)  # 390 chars
        self.logCmd("c" * 400)  # 400 chars
        self.logCmd("c" * 410)  # 410 chars
        # default is 400 char limit
        self.check_without_ts(self.query(""), ["c" * 390, "c" * 400])
        # Check with explicit limits
        self.check_without_ts(self.query("-cl 390"), ["c" * 390])
        self.check_without_ts(self.query("--char_limit 390"), ["c" * 390])
        self.check_without_ts(self.query("--char_limit 400"), ["c" * 390, "c" * 400])
        self.check_without_ts(self.query("--char_limit 410"), ["c" * 390, "c" * 400, "c" * 410])

    @tests_option("cur_session_only")
    def test_cur_session(self):
        self.initSession(1)
        self.initSession(2)
        self.logCmd("shell1 1", shell_pid=1)
        self.logCmd("shell1 2", shell_pid=1)
        self.logCmd("shell2 1", shell_pid=2)
        self.logCmd("shell2 2", shell_pid=2)
        with mock.patch('os.getppid', return_value=1):
            self.check_without_ts(self.query("-cs 1"), ["shell1 1", "shell1 2"])
            self.check_without_ts(self.query("--cur_session_only 1"), ["shell1 1", "shell1 2"])

        with mock.patch('os.getppid', return_value=2):
            self.check_without_ts(self.query("-cs 2"), ["shell2 1", "shell2 2"])
            self.check_without_ts(self.query("--cur_session_only 2"), ["shell2 1", "shell2 2"])

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

    @tests_option("re")
    def test_re(self):
        cmds = [
            "head common 0only tail",
            "head 1only common tail",
        ]
        self.logCmd(cmds[0])
        self.logCmd(cmds[1])
        self.check_without_ts(self.query("-re common"), cmds)
        self.check_without_ts(self.query("-re head.*tail"), cmds)
        self.check_without_ts(self.query("-re head.*0.*tail"), [cmds[0]])
        self.check_without_ts(self.query("-re head.*1.*tail"), [cmds[1]])

    @tests_option("sql")
    def test_sql(self):
        cmds = [
            "head common 0only tail",
            "head 1only common tail",
        ]
        self.logCmd(cmds[0])
        self.logCmd(cmds[1])
        self.check_without_ts(self.query_with_args(["-sql", """command like '%common%'"""]), cmds)
        self.check_without_ts(self.query_with_args(["-sql", """command like 'head%tail'"""]), cmds)
        self.check_without_ts(
            self.query_with_args(
                ["-sql", ("""command like 'head%tail' """
                          """AND command not like '%1only%'""")]), [cmds[0]])
        self.check_without_ts(
            self.query_with_args(
                ["-sql", ("""command like 'head%tail' """
                          """AND command like '%1only%'""")]), [cmds[1]])

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

    @tests_option("d")
    def test_date(self):
        def ts_for_date(date_str):
            yr, m, day = map(int, date_str.split("-"))
            import datetime
            # 12 pm on the given day
            return datetime.datetime(yr, m, day, hour=12).timestamp()

        self.logCmd("cmd 2019-07-01", time_secs=ts_for_date("2019-07-01"))
        self.logCmd("cmd 2020-06-01", time_secs=ts_for_date("2020-06-01"))
        self.logCmd("cmd 2020-07-01", time_secs=ts_for_date("2020-07-01"))
        self.logCmd("cmd 2020-07-02", time_secs=ts_for_date("2020-07-02"))

        self.check_without_ts(self.query("-d 2020"),
                              ["cmd 2020-06-01", "cmd 2020-07-01", "cmd 2020-07-02"])
        self.check_without_ts(self.query("-d 2020-07"), ["cmd 2020-07-01", "cmd 2020-07-02"])
        self.check_without_ts(self.query("-d 2020-07-01"), ["cmd 2020-07-01"])

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
        self.check_without_ts(
            self.query("--env RECENT_CAPTURE"),
            ["capture_set1", "capture_set1 again", "capture_set2", "capture_set2 again"])
        self.check_without_ts(
            self.query("--env EXPLICIT_CAPTURE"),
            ["capture_set1", "capture_set1 again", "capture_set2", "capture_set2 again"])
        # Query by env var value.
        self.check_without_ts(self.query("--env EXPLICIT_CAPTURE:explicit1"),
                              ["capture_set1", "capture_set1 again"])
        self.check_without_ts(self.query("--env EXPLICIT_CAPTURE:explicit2"),
                              ["capture_set2", "capture_set2 again"])
        self.check_without_ts(self.query("--env RECENT_CAPTURE:implicit1"),
                              ["capture_set1", "capture_set1 again"])
        self.check_without_ts(self.query("--env RECENT_CAPTURE:implicit2"),
                              ["capture_set2", "capture_set2 again"])

    @tests_option("debug")
    def tests_debug_does_not_throw_error(self):
        self.logCmd("cmd1")
        self.logCmd("cmd2")
        res = self.query("--debug")
        cmd1_found, cmd2_found = False, False
        for r in res:
            if "cmd1" in r:
                cmd1_found = True
            elif "cmd2" in r:
                cmd2_found = True
        self.assertTrue(cmd1_found and cmd2_found)

    def test_recent_custom_prompt(self):
        # If you set RECENT_CUSTOM_PROMPT, PROMPT_COMMAND check will be skipped.
        os.environ['RECENT_CUSTOM_PROMPT'] = 'something'
        os.environ['PROMPT_COMMAND'] = 'something'
        with mock.patch('sys.exit') as exit_mock:
            recent2.check_prompt(False)
            self.assertFalse(exit_mock.called)

        del os.environ['PROMPT_COMMAND']
        with mock.patch('sys.exit') as exit_mock:
            recent2.check_prompt(False)
            self.assertFalse(exit_mock.called)

    def test_check_prompt(self):
        # PROMPT_COMMAND will be checked.
        os.environ['PROMPT_COMMAND'] = recent2.EXPECTED_PROMPT
        with mock.patch('sys.exit') as exit_mock:
            recent2.check_prompt(False)
            self.assertFalse(exit_mock.called)

        os.environ['PROMPT_COMMAND'] = 'something'
        with mock.patch('sys.exit') as exit_mock:
            recent2.check_prompt(False)
            self.assertTrue(exit_mock.called)
            # First argument in first call to exit_mock
            exit_arg = exit_mock.call_args[0][0]
            self.assertTrue('PROMPT_COMMAND' in exit_arg and recent2.EXPECTED_PROMPT in exit_arg)

        del os.environ['PROMPT_COMMAND']
        with mock.patch('sys.exit') as exit_mock:
            recent2.check_prompt(False)
            self.assertTrue(exit_mock.called)
            # First argument in first call to exit_mock
            exit_arg = exit_mock.call_args[0][0]
            self.assertTrue('PROMPT_COMMAND' in exit_arg and recent2.EXPECTED_PROMPT in exit_arg)

    @tests_option("dedup")
    def test_dedup(self):
        base_pid = self._shell_pid
        for i in range(1, 5):
            self.initSession(base_pid + i)

        self.logCmd("cmd 1", pwd="/dir1", shell_pid=base_pid + 1, time_secs=1, return_value=0)
        self.logCmd("cmd 2", pwd="/dir1", shell_pid=base_pid + 2, time_secs=2, return_value=0)
        # Log same commands as above. But use different shells. Ensure that
        # the code handles same comment, but different dir properly.
        self.logCmd("cmd 1", pwd="/dir2", shell_pid=base_pid + 3, time_secs=3, return_value=1)
        self.logCmd("cmd 2", pwd="/dir2", shell_pid=base_pid + 4, time_secs=4, return_value=1)

        self.check_with_ts(self.query("cmd --dedup"), [("cmd 1", 3), ("cmd 2", 4)])
        self.check_with_ts(self.query("cmd --dedup -so"), [("cmd 1", 1), ("cmd 2", 2)])
        self.check_with_ts(self.query("cmd --dedup -fo"), [("cmd 1", 3), ("cmd 2", 4)])


class LogCommandTest(TestBase):
    # log() method will not be tested here because we have enough coverage in RecentTest

    def test_log_entry_point(self):
        os.environ['PWD'] = '/cur_pwd'
        with mock.patch('recent2.log_command') as log_command:
            recent2.log(["-r", "12", "-c", "123 my_cmd", "-p", "1234"])
            log_command.assert_called_with(command="my_cmd", pid=1234, sequence=123,
                                           return_value=12, pwd="/cur_pwd")

            ts = "# rtime@ 2020-07-20 21:52:33"
            # log command discards if the command being logged has a suffix like "my_cmd <ts>"
            # If a user copy-pastes recent output, having this timestamp will look weird.
            recent2.log(["-r", "12", "-c", f"123 cmd1 {ts}", "-p", "1234"])
            log_command.assert_called_with(command="cmd1", pid=1234, sequence=123,
                                           return_value=12, pwd="/cur_pwd")

            # Extra trailing space. timestamp will not be trimmed.
            recent2.log(["-r", "12", "-c", f"123 cmd_extra_space {ts} ", "-p", "1234"])
            log_command.assert_called_with(command=f"cmd_extra_space {ts} ", pid=1234, sequence=123,
                                           return_value=12, pwd="/cur_pwd")

    def test_parse_history(self):
        cmd = "cmd arg1 arg2 arg3"
        self.assertEqual(recent2.parse_history("1234 " + cmd), (1234, cmd))
        self.assertEqual(recent2.parse_history(" 123   " + cmd), (123, cmd))
        self.assertEqual(recent2.parse_history(" 12  " + cmd), (12, cmd))
        self.assertEqual(recent2.parse_history("no_number " + cmd), (None, None))


class ImportBashHistory(TestBase):
    def setUp(self) -> None:
        super().setUp()
        self.import_marker = "/tmp/{}".format(uuid.uuid1())
        self.history_file = "/tmp/{}".format(uuid.uuid1())
        os.environ['RECENT_TEST_IMPORT_FILE'] = self.import_marker
        os.environ['HISTFILE'] = self.history_file

    # Calls import_bash_history_entry_point and returns stdout.
    def import_history(self, expect_failure=False, args=None):
        def work():
            if expect_failure:
                with self.assertRaises(SystemExit) as cm:
                    return recent2.import_bash_history_entry_point(args)
                self.assertNotEqual(cm.exception.code, 0)
            else:
                return recent2.import_bash_history_entry_point(args)

        with mock.patch('sys.stdout', new=io.StringIO()) as fake_out:
            work()
        return fake_out.getvalue()

    def helper_for_test_import(self, import_args=None):
        def time_history_line():
            now = self._time_secs
            self._time_secs += 1
            return "#{}".format(int(now))

        lines = [
            time_history_line(),
            "cmd1",
            time_history_line(),
            "cmd2",
            "cmd3",  # This command has no timestamp.
            time_history_line(),
            "cmd4",  # This command has timestamp again.
        ]
        content = "\n".join(lines)
        Path(self.history_file).write_text(content)
        # Import history
        self.import_history(args=import_args)
        # Check that we actually imported history
        # Note:
        # - we are not testing timestamps.
        # - we are checking for cmd3 before cmd2 because cmd3 will get cmd2's timestamp and
        #   sqlite returns latest inserted item first.
        self.check_without_ts(self.query(""), ["cmd1", "cmd3", "cmd2", "cmd4"])
        self.assertTrue(Path(self.import_marker).exists())

    def test_import(self):
        # Expected case.
        self.helper_for_test_import()

    def test_import_force(self):
        # Import marker exists, but we will run with -f argument to import
        # again.
        Path(self.import_marker).touch()
        self.helper_for_test_import(["-f"])

    def test_import_marker_exists(self):
        # Import marker exists. So import will fail.
        Path(self.import_marker).touch()
        # Import marker exists => failure
        stdout = self.import_history(expect_failure=True)
        self.assertTrue('Bash history already imported' in stdout)


if __name__ == '__main__':
    unittest.main()
