# Print the commands we are running
set -o xtrace
# exit when any command fails
set -e

# Ensure that recent2 is not installed.
pip uninstall --yes recent2 || true
python setup.py bdist_wheel
pip install dist/recent2-*-py3-none-any.whl
# update prompt command. Otherwise recent command will fail.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
# Explicitly log some command with pid 4556 and return value 0
log-recent -r 0 -c " 123 some command" -p 4556
# Explicitly log some other with pid 4556 and return value 0
log-recent -r 1 -c " 124 some other command" -p 3455
# Run the recent command just so that we know it kind of works.
recent > /tmp/out
# Grep for the commands. Grep returns failure if it does not find the text.
grep "some command" /tmp/out
grep "some other command" /tmp/out