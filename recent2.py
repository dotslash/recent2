#!/usr/bin/env python
import json
import sqlite3
import os
import argparse
import hashlib
import re
import socket
from pathlib import PurePath

SCHEMA_VERSION = 2


class Term:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class SQL:
    CASE_ON = "PRAGMA case_sensitive_like = true"
    GET_COMMANDS_TABLE_SCHEMA = """
        select sql from sqlite_master where type = 'table' and name = 'commands';"""
    INSERT_ROW_CUSTOM_BASE = """insert into commands
        (command_dt, command, pid, return_val, pwd, session, json_data)
        values ({}, ?, ?, ?, ?, ?, {})"""
    # Replace INSERT_ROW_CUSTOM_BASE's first param with datatime and 2nd param with {} again.
    # NOTE(dotslash): I haven't found a way to send json using ?s. So doing with string formats.
    INSERT_ROW = INSERT_ROW_CUSTOM_BASE.format("datetime('now', 'localtime')", "{}")
    INSERT_ROW_CUSTOM_TS = INSERT_ROW_CUSTOM_BASE.format("datetime(?, 'unixepoch')", "null")
    INSERT_SESSION = """insert into sessions (created_dt, updated_dt,
        term, hostname, user, sequence, session)
        values (datetime('now','localtime'), datetime('now','localtime'), ?, ?, ?, ?, ?)"""
    UPDATE_SESSION = """update sessions set updated_dt = datetime('now','localtime'), sequence = ?
        where session = ?"""
    # TAIL_N_ROWS's columns (column order is same as TAIL_N_ROWS
    COLUMNS = 'command_dt,command,pid,return_val,pwd,session,json_data'.split(',')
    TAIL_N_ROWS = """select command_dt, command, pid, return_val, pwd, session, json_data
                     from (select * from commands where
                     order by command_dt desc limit ?) order by command_dt"""
    GET_SESSION_SEQUENCE = """select sequence from sessions where session = ?"""

    # Setup: Create tables.
    CREATE_COMMANDS_TABLE = """create table if not exists commands
        (command_dt timestamp, command text, pid int, return_val int, pwd text, session text,
         json_data json)"""
    CREATE_SESSIONS_TABLE = """create table if not exists sessions
        (session text primary key not null, created_dt timestamp, updated_dt timestamp,
        term text, hostname text, user text, sequence int)"""
    CREATE_DATE_INDEX = """create index if not exists command_dt_ind on commands (command_dt)"""
    # Schema version
    GET_SCHEMA_VERSION = """pragma user_version"""
    UPDATE_SCHEMA_VERSION = """pragma user_version = """
    # Migrate from v1 to v2.
    MIGRATE_1_2 = "alter table commands add column json_data json"


class Session:

    def __init__(self, pid, sequence):
        self.sequence = sequence
        self.empty = False
        # This combination of ENV vars *should* provide a unique session
        # TERM_SESSION_ID for OS X Terminal
        # XTERM for xterm
        # TMUX, TMUX_PANE for tmux
        # STY for GNU screen
        # SHLVL handles nested shells
        seed = "{}-{}-{}-{}-{}-{}-{}".format(
            os.getenv('TERM_SESSION_ID', ''),
            os.getenv('WINDOWID', ''),
            os.getenv('SHLVL', ''),
            os.getenv('TMUX', ''),
            os.getenv('TMUX_PANE', ''),
            os.getenv('STY', ''),
            pid)
        self.id = hashlib.md5(seed.encode('utf-8')).hexdigest()

    def update(self, conn):
        c = conn.cursor()
        try:
            term = os.getenv('TERM', '')
            hostname = socket.gethostname()
            user = os.getenv('USER', '')
            c.execute(SQL.INSERT_SESSION,
                      [term, hostname, user, self.sequence, self.id])
            self.empty = True
        except sqlite3.IntegrityError:
            # Carriage returns need to be ignored
            if c.execute(SQL.GET_SESSION_SEQUENCE, [self.id]).fetchone()[0] == int(self.sequence):
                self.empty = True
            c.execute(SQL.UPDATE_SESSION, [self.sequence, self.id])


def migrate(version, conn):
    if version not in (0, 1):
        exit(Term.FAIL + ('recent: your command history database does not '
                          'match recent, please update') + Term.ENDC)

    c = conn.cursor()
    if version == 1:
        # Schema version is v1. Migrate to v2.
        print(Term.WARNING +
              'recent: migrating schema to version {}'.format(SCHEMA_VERSION) +
              Term.ENDC)
        c.execute(SQL.MIGRATE_1_2)
    else:
        print(Term.WARNING + 'recent: building schema' + Term.ENDC)
        c.execute(SQL.CREATE_COMMANDS_TABLE)
        c.execute(SQL.CREATE_SESSIONS_TABLE)
        c.execute(SQL.CREATE_DATE_INDEX)

    c.execute(SQL.UPDATE_SCHEMA_VERSION + str(SCHEMA_VERSION))
    conn.commit()


def parse_history(history):
    match = re.search(r'^\s+(\d+)\s+(.*)$', history,
                      re.MULTILINE and re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    else:
        return None, None


def parse_date(date_format):
    if re.match(r'^\d{4}$', date_format):
        return 'strftime(\'%Y\', command_dt) = ?'
    if re.match(r'^\d{4}-\d{2}$', date_format):
        return 'strftime(\'%Y-%m\', command_dt) = ?'
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_format):
        return 'date(command_dt) = ?'
    else:
        return 'command_dt = ?'


def create_connection():
    recent_db = os.getenv('RECENT_DB', os.environ['HOME'] + '/.recent.db')
    conn = sqlite3.connect(recent_db)
    build_schema(conn)
    return conn


def build_schema(conn):
    try:
        c = conn.cursor()
        current = c.execute(SQL.GET_SCHEMA_VERSION).fetchone()[0]
        if current != SCHEMA_VERSION:
            migrate(current, conn)
    except (sqlite3.OperationalError, TypeError):
        migrate(0, conn)


def envvars_to_log():
    envvar_whitelist = {k.strip() for k in os.getenv('RECENT_ENV_VARS', '').split(',') if k.strip()}

    def is_var_interesting(name: str):
        # Anything starting with RECENT_ is welcome.
        if name.startswith("RECENT_"):
            return True
        for interesting_var in envvar_whitelist:
            # if name matches glob(interesting_var) then we will store it.
            # E.g - CONDA_* => we are interested in all env vars that start with CONDA_.
            if PurePath(name).match(interesting_var):
                return True
        return False

    return {k: v for k, v in os.environ.items() if is_var_interesting(k)}


# Entry point to recent-log command.
def log():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--return_value', help='set to $?', default=0)
    parser.add_argument('-c', '--command',
                        help='set to $(HISTTIMEFORMAT= history 1)', default='')
    parser.add_argument('-p', '--pid', help='set to $$', default=0)
    args = parser.parse_args()

    sequence, command = parse_history(args.command)
    pid, return_value = args.pid, args.return_value
    pwd = os.getenv('PWD', '')

    if not sequence or not command:
        print(Term.WARNING +
              ('recent: cannot parse command output, please check your bash '
               'trigger looks like this:') +
              Term.ENDC)
        print("""export PROMPT_COMMAND="""
              """'log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'""")
        exit(1)

    conn = create_connection()
    session = Session(pid, sequence)
    session.update(conn)

    if not session.empty:
        c = conn.cursor()
        json_data = "json('{}')".format(json.dumps({'env': envvars_to_log()}))
        c.execute(SQL.INSERT_ROW.format(json_data), [command, pid, return_value, pwd, session.id])

    conn.commit()
    conn.close()


# Imports bash_history into RECENT_DB
# Entry point to recent-import-bash-history command.
def import_bash_history_entry_point():
    description = ('recent-import-bash-history imports bash_history into ~/.recent.db. '
                   'Run `recent -h` for info about recent command.')
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-f',
                        help='Force import bash history ignoring previous imports',
                        action='store_true')
    args = parser.parse_args()
    import_file = os.path.expanduser("~/.recent_imported_bash_history")
    if not args.f and os.path.exists(import_file):
        print(Term.FAIL +
              'recent-import-bash-history failed: Bash history already imported into ~/.recent.db')
        print('Run the command with -f option if you are absolutely sure.' + Term.ENDC)
        parser.print_help()
        exit(1)
    import_bash_history()
    open(import_file, 'a').close()


def import_bash_history():
    # Construct history from bash_history.
    # Example bash_history. The history has 3 entries. First entry has no timestamp attached to it.
    # The next 2 entries have timestamp attached to them. The last entry has some unknown comment
    # which we will ignore.
    """
    ls /
    #1571012545
    echo foo
    #1571012560
    #useless comment that should be ignored.
    cat bar
    """
    history = []
    # Phase 1 starts: After this phase history will be like this
    # [(-1, "ls /"), # This entry has no timestamp.
    #  (1571012545, "echo foo"),
    #  (1571012560, "cat bar")]
    last_ts = -1
    for line in open(os.path.expanduser("~/.bash_history")):
        if line[0] == '#':
            try:
                last_ts = int(line[1:].strip())
            except Exception:
                # Ignore the exception.
                pass
            continue
        history.append([last_ts, line.strip()])

    # Phase 2 starts: After this phase history will be like this
    # [(1571012545, "ls /"), # Timestamp for this comes from its next entry
    #  (1571012545, "echo foo"),
    #  (1571012560, "cat bar")]
    last_ts = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i][0] == -1 and last_ts != -1:
            history[i][0] = last_ts
        elif history[i][0] != -1 and last_ts == -1:
            last_ts = history[i][0]
    # Add the history entries into recent's DB.
    conn = create_connection()
    import random
    # Create a session with a random -ve pid and random -ve sequence id.
    pid = -random.randint(1, 10000000)
    session = Session(pid=pid, sequence=-random.randint(1, 10000000))
    session.update(conn)
    for cmd_ts, cmd in history:
        c = conn.cursor()
        c.execute(SQL.INSERT_ROW_CUSTOM_TS, [
            cmd_ts, cmd, pid,
            # exit status=-1, working directory=/unknown
            -1, "/unknown",
            session.id, ""])
    conn.commit()
    conn.close()


# Returns a list of queries to run for the given args
# Return type: List(Pair(query, List(query_string)))
def query_builder(args, parser):
    if args.re and args.sql:
        print(Term.FAIL + 'Only one of -re and -sql should be set' + Term.ENDC)
        parser.print_help()
        exit(1)
    num_status_filter = sum(
        1 for x in [args.successes_only, args.failures_only, args.status_num != -1] if x)
    if num_status_filter > 1:
        print(Term.FAIL +
              ('Only one of --successes_only, --failures_only and '
               '--status_num has to be set') +
              Term.ENDC)
        parser.print_help()
        exit(1)
    query = SQL.TAIL_N_ROWS
    filters = []
    parameters = []
    if args.successes_only:
        filters.append('return_val = 0')
    if args.failures_only:
        filters.append('return_val <> 0')
    if args.status_num != -1:
        filters.append('return_val == ?')
        parameters.append(args.status_num)
    if not args.return_self:
        # Dont return recent commands unless user asks for it.
        filters.append("""command not like 'recent%'""")
    if args.pattern:
        if args.re:
            filters.append('command REGEXP ?')
            parameters.append(args.pattern)
        elif args.sql:
            filters.append(args.pattern)
        else:
            filters.append('command like ?')
            parameters.append('%' + args.pattern + '%')
    if args.w:
        filters.append('pwd = ?')
        parameters.append(os.path.abspath(os.path.expanduser(args.w)))
    if args.d:
        filters.append(parse_date(args.d))
        parameters.append(args.d)
    for env_var in args.env:
        split = env_var.split(":")
        if len(split) == 1:
            filters.append('json_extract(json_data, "$.env.{}") is not null'.format(split[0]))
        else:
            filters.append('json_extract(json_data, "$.env.{}") = ?'.format(split[0]))
            parameters.append(split[1])
    filters.append('length(command) < {}'.format(args.char_limit))
    try:
        n = int(args.n)
        parameters.append(n)
    except:
        exit(Term.FAIL + '-n must be a integer' + Term.ENDC)
    where = 'where ' + ' and '.join(filters) if len(filters) > 0 else ''

    ret = []
    if not args.nocase:
        # No params required for case on query.
        ret.append((SQL.CASE_ON, []))
    query_and_params = query.replace('where', where), parameters
    ret.append(query_and_params)
    return ret


# Returns true if `item` matches `expr`. Used as sqlite UDF.
def regexp(expr, item):
    reg = re.compile(expr)
    return reg.search(item) is not None


def make_arg_parser_for_recent():
    description = ('recent is a convenient way to query bash history. '
                   'Visit {} for more examples or to ask questions or to report issues'
                   ).format(Term.UNDERLINE + 'https://github.com/dotslash/recent2' + Term.ENDC)
    epilog = 'To import bash history into recent db run {}'.format(
        Term.UNDERLINE + 'recent-import-bash-history' + Term.ENDC)
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument(
        'pattern', nargs='?',
        default='', help='optional pattern to search')
    parser.add_argument('-n', metavar='20',
                        help='max results to return', default=20)

    # Filters for command success/failure.
    parser.add_argument('--status_num', '-stn', metavar='0',
                        help='int exit status of the commands to return. -1 => return all.',
                        default=-1)
    parser.add_argument('--successes_only', '-so',
                        help='only return commands that exited with success',
                        action='store_true')
    parser.add_argument('--failures_only', '-fo',
                        help='only return commands that exited with failure',
                        action='store_true')
    # Other filters/options.
    parser.add_argument('-w', metavar='/folder',
                        help='working directory', default='')
    parser.add_argument(
        '-d', metavar='2016-10-01',
        help='date in YYYY-MM-DD, YYYY-MM, or YYYY format', default='')
    parser.add_argument(
        '--return_self',
        help='Return `recent` commands also in the output',
        action='store_true')
    parser.add_argument(
        '--char_limit', '-cl',
        metavar='200',
        help='Ignore commands longer than this.',
        default=200)
    parser.add_argument(
        '-e', '--env',
        action='append',
        help='Filter by shell env vars',
        metavar='key[:val]',
        default=[])

    # CONTROL OUTPUT FORMAT
    # Hide time. This makes copy-pasting simpler.
    parser.add_argument(
        '--hide_time', '-ht',
        help='dont display time in command output', action='store_true')
    parser.add_argument('--debug', help='Debug mode', action='store_true')
    parser.add_argument('--detail', help='Return detailed output', action='store_true')
    parser.add_argument(
        '--columns',
        help=('Comma separated columns to print if --detail is passed. Valid columns are '
              'command_dt,command,pid,return_val,pwd,session,json_data'),
        default="command_dt,command,json_data")

    # Query type - regex/sql.
    parser.add_argument(
        '-re', help='enable regex search pattern', action='store_true')
    parser.add_argument(
        '-sql', help='enable sqlite search pattern', action='store_true')
    parser.add_argument(
        '--nocase', '-nc',
        help='Ignore case when searching for patterns', action='store_true')
    return parser


def check_prompt():
    import os
    expected_prompt = 'log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
    actual_prompt = os.environ.get('PROMPT_COMMAND', '')
    export_promot_cmd = \
        '''export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$' '''
    if expected_prompt not in actual_prompt:
        print(Term.BOLD +
              "PROMPT_COMMAND env variable is not set. " +
              "Add the following line to .bashrc or .bash_profile" +
              Term.ENDC)

        print(Term.UNDERLINE + export_promot_cmd + Term.ENDC)
        exit(1)


# Entry point to recent command.
def main():
    check_prompt()  # Fail the command if PROMPT_COMMAND is not set
    parser = make_arg_parser_for_recent()
    args = parser.parse_args()
    conn = create_connection()
    # Install REGEXP sqlite UDF.
    conn.create_function("REGEXP", 2, regexp)
    # Register the queries executed. (Replace new lines with spaces in the query)
    queries_executed = []

    def update_queries_executed(inp):
        if inp == SQL.GET_COMMANDS_TABLE_SCHEMA:
            return
        trans = inp.replace('\n', ' ')
        queries_executed.append(trans)

    conn.set_trace_callback(update_queries_executed)
    c = conn.cursor()
    detail_results = []
    columns_to_print = args.columns.split(',')
    columns_to_print.extend(['command_dt', 'command'])
    for query, parameters in query_builder(args, parser):
        for row in c.execute(query, parameters):
            row_dict = {SQL.COLUMNS[i]: row[i]
                        for i in range(len(row))
                        if SQL.COLUMNS[i] in columns_to_print}
            if 'command_dt' not in row_dict or 'command' not in row_dict:
                # Why would we have these entries?
                continue
            if args.detail:
                detail_results.append(row_dict)
                continue
            if args.hide_time:
                print(row_dict['command'])
            if not args.hide_time:
                print(Term.WARNING + row_dict['command_dt'] + Term.ENDC + ' ' + row_dict['command'])
    if args.detail:
        if 'json_data' not in columns_to_print:
            from tabulate import tabulate
            print(tabulate(detail_results, headers="keys"))
        else:
            for res in detail_results:
                for k, v in res.items():
                    print(Term.BOLD + Term.OKBLUE + k + Term.ENDC + ": " + str(v))
                print("---------------------------------")

    if args.debug:
        schema = None
        for row in c.execute(SQL.GET_COMMANDS_TABLE_SCHEMA, []):
            schema = row[0]
        print("=========DEBUG=========")
        print("---SCHEMA---")
        print(schema)
        print("---QUERIES---")
        print("To replicate(ish) this output run the following sqlite command")
        print("""sqlite3 ~/.recent.db "{}" """.format('; '.join(queries_executed)))
    conn.close()


if __name__ == '__main__':
    print("=================")
    print("Executing recent from __main__.")
    print("This means recent2 is being run via `python recent2.py`")
    print("=================")
    main()
