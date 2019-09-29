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
`recent2` repo is a clone of [trengrj/recent](https://github.com/trengrj/recent). 
I made a clone because I want to make some changes to the util and 
[trengrj](https://github.com/trengrj) has not been very responsive. Most of the
code is written by [trengrj](https://github.com/trengrj)

## Installation instructions

You need will need sqlite installed.

Install the recent pip package.

`pip install recent2`

Add the following to your `.bashrc` or `.bash_profile`.

`export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'`

And start a new shell.

## Usage

See example usage at https://asciinema.org/a/271533

Look at your current history using recent. Here are some examples on how to use recent.

```sh
# Help
recent -h
# Look for all git commands
recent git
# Look for git commit commands.
# Query via regexp mode.
recent -re git.*commit
# Look for git commands that are not commits.
# Query via sql mode.
recent -sql 'command like "%git%" and command not like "%commit%"'
```

By default `recent` commands are not displayed in the output. To see the `recent` commands pass
the `return_self` argument as follows.

`recent git --return_self`

For more information run `recent -h`

You can directly query your history running `sqlite3 ~/.recent.db "select * from commands limit 10"`

## Dev installation instructions
```
git clone https://github.com/dotslash/recent2 && cd recent2
pip install -e .
```
