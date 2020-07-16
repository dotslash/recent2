# Print the commands we are running
set -o xtrace
# exit when any command fails
set -e


# Ensure that recent2 is not installed.
pip uninstall --yes recent2 || true
python setup.py bdist_wheel
pip install dist/recent2-*-py3-none-any.whl

### LET'S DO SOME VERY BASIC TESTING ###

# update prompt command. Otherwise recent command will fail.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'

# Manually add elements to bash history.
export HISTFILE=~/.bash_history
history -s "bash history before recent1"
history -s "bash history before recent2"
history -w
echo $HISTFILE
cat $HISTFILE
# Import bash history.
recent-import-bash-history
# Check for the imported bash history.
recent > /tmp/out
grep "bash history before recent1" /tmp/out
grep "bash history before recent1" /tmp/out
# Initialize the session for pid 4556.
# "command from different session" will not be recorded.
log-recent -r 0 -c " 122 command from different session" -p 4556
# Explicitly log "some command" return value 0
log-recent -r 0 -c " 123 some command" -p 4556
# Explicitly log "some other command" return value 1
log-recent -r 1 -c " 124 some other command" -p 4556
# https://github.com/dotslash/recent2/pull/33
log-recent -r 0 -c "125 no space before history number" -p 4556

# Run recent command and output to a tmp file.
recent > /tmp/out
# Grep for the commands. Grep returns failure if it does not find the text.
cat /tmp/out # For debugging.
grep "some command" /tmp/out
grep "some other command" /tmp/out
grep "no space before history number" /tmp/out

# Check that the tmp file does not contain the unexpected command
OUT="does_not_contain"
(grep "command from different session" /tmp/out && OUT="contains") || true
[[ $OUT == "does_not_contain" ]]
