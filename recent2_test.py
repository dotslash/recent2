import io
import os
import time
import unittest
import unittest.mock as mock

import recent2


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
            return fake_out.getvalue().strip().split("\n")

    def check_without_ts(self, result_lines, expected_lines):
        time_template = recent2.Term.WARNING + "2020-07-20 21:52:33 " + recent2.Term.ENDC
        # Strip the time prefix on the results before comparing.
        result_lines = [r[len(time_template):] for r in result_lines]
        self.assertEqual(result_lines, expected_lines)

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


if __name__ == '__main__':
    unittest.main()
