set -o xtrace
# Install recent from a different directory
code_dir=$(pwd)
echo $code_dir
cd $HOME
pwd
pip install -e $code_dir
# update prompt command.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
# Run some commands.
echo "wow"
date
# check if recent shows these.
recent
