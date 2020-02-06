set -o xtrace # Print the commands we are running
# Install `recent` from a different directory. By running from different
# dir, we will verify that we are not relying on files in the directory
# and not files we export in the python package.
# TODO(dotslash): May be upload to test pypi and install it.
code_dir=$(pwd)
echo $code_dir
cd $HOME
pwd
pip uninstall recent2 || true
pip install -e $code_dir
# update prompt command. Otherwise recent command will fail.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
recent # Run the recent command just so that we know it kind of works.
