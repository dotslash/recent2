# Recent

Recent is a more structured way to log your bash history.

The standard `~/.bash_history` file is inadequate in many ways, its
worst fault is to by default log only 500 history entries, with no timestamp.
You can alter your bash `HISTFILESIZE` and `HISTTIMEFORMAT` variables but it
is still a unstructured format with limited querying ability.

Recent does the following.

1. Logs current localtime, command text, current pid, command return value,
   working directory to an sqlite database in `~/.recent.db`.
2. Logs history immediately, rather than at the close of the session.
3. Provides a command called `recent` for searching bash history.

## NOTE about [trengrj/recent](https://github.com/trengrj/recent)

`recent2` is a clone of [trengrj/recent](https://github.com/trengrj/recent). I
used [trengrj](https://github.com/trengrj)'s util for about a month and I really
liked it. However I saw some short comings in the tool. I made a clone because
trengrj has not been very responsive.

Most of the code is written by [trengrj](https://github.com/trengrj). I only added
a few incremental patches; but I intend to actively maintain this as I see more
interesting use cases.

## Installation instructions

You need will need sqlite installed.

Install the recent pip package.

`pip install recent2`

Add the following to your `.bashrc` or `.bash_profile`.

`export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'`

And start a new shell.

## Usage

See example usage at https://asciinema.org/a/271533

### Help Text

```sh
> recent -h
usage: recent [-h] [-n 20] [--status_num 0] [--successes_only]
              [--failures_only] [-w /folder] [-d 2016-10-01] [--return_self]
              [--hide_time] [-re] [-sql]
              [pattern]

recent is a convinient way to query bash history. Visit
https://github.com/dotslash/recent2 for more examples or to ask
questions or to report issues

positional arguments:
  pattern               optional pattern to search

optional arguments:
  -h, --help            show this help message and exit
  -n 20                 max results to return
  --status_num 0, -stn 0
                        int exit status of the commands to return. -1 =>
                        return all.
  --successes_only, -so
                        only return commands that exited with success
  --failures_only, -fo  only return commands that exited with failure
  -w /folder            working directory
  -d 2016-10-01         date in YYYY-MM-DD, YYYY-MM, or YYYY format
  --return_self         Return `recent` commands also in the output
  --hide_time, -ht      dont display time in command output
  -re                   enable regex search pattern
  -sql                  enable sqlite search pattern

To import bash history into recent db run recent-import-bash-history
```

Look at your current history using recent. Here are some examples on how to use recent.

### Basic examples

```sh
# Look for all git commands
recent git
# Look for git commit commands. Query via regexp mode.
recent -re git.*commit
```

### Less basic usage

- Filter commands by exit status
  1. `recent git --successes_only` or `recent git -so`
  2. `recent git --failures_only` or `recent git -fo`
  3. `recent git --status_num 1` or `recent git -stn 1` returns only the git commands that have exit status 1.
- `recent git --return_self`. By default `recent` commands are not displayed in the output. Pass the `return_self` to change that.
- `recent git -w ~/code`. This returns only the commands that were executed with `~/code` as current working directory.
- Filter the commands by execution date by doing `recent git -d 2019` or `recent git -d 2019-10` or `recent git -d 2019-10-04`
- By default recent prints command timestamp and the command in the output. Use `recent git --hide_time` or `recent git -ht` to hide the command timestamp. This is useful when copy-pasting commands from output.

### Usage via sqlite

It is possible directly interact with sqlite if all the above options have failed you. See the table schema below.

```sql
CREATE TABLE commands(
  command_dt timestamp,
  command text,
  pid int,
  return_val int,
  pwd text,
  session text);
CREATE INDEX command_dt_ind on commands (command_dt);
```

- option1: `recent -sql 'command like "%git%" and command not like "%commit%"'`
- option2: You can directly play around with sqlite `sqlite3 ~/.recent.db "select * from commands limit 10"`

## Dev installation instructions

```sh
git clone https://github.com/dotslash/recent2 && cd recent2
pip install -e .
```
