set -o xtrace
# Install recent
pip install -e .
# update prompt command.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
# Run some commands.
echo "wow"
date
# check if recent shows these.
recent
