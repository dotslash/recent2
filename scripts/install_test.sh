set -o xtrace # Print the commands we are running
# Ensure that recent2 is not installed.
pip uninstall --yes recent2 || true
python setup.py bdist_wheel
pip install dist/recent2-*-py3-none-any.whl
# update prompt command. Otherwise recent command will fail.
export PROMPT_COMMAND='log-recent -r $? -c "$(HISTTIMEFORMAT= history 1)" -p $$'
ls .
echo "wow"
recent # Run the recent command just so that we know it kind of works.
