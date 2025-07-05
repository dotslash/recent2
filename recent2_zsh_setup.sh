# recent2 zsh setup
#
# To enable recent2 logging in zsh, add the following to your ~/.zshrc file:
#
# autoload -U add-zsh-hook
#
# _recent2_preexec() {
#   # Capture command text. The third argument to preexec is the full command text.
#   # Only store if it's not empty.
#   if [[ -n "$3" ]]; then
#       # Store the command text in a global variable.
#       # Using a specific prefix to avoid clashes.
#       _RECENT2_CURRENT_COMMAND_TEXT="$3"
#
#       # Try to get the history number. HISTCMD is the history number of the current command line.
#       # This should be available before the command executes.
#       _RECENT2_CURRENT_COMMAND_SEQ="$HISTCMD"
#   else
#       # Clear if no command text (e.g. just hitting enter on empty prompt)
#       unset _RECENT2_CURRENT_COMMAND_TEXT
#       unset _RECENT2_CURRENT_COMMAND_SEQ
#   fi
# }
#
# _recent2_precmd() {
#   # Check if a command was captured by preexec
#   if [[ -n "$_RECENT2_CURRENT_COMMAND_TEXT" && -n "$_RECENT2_CURRENT_COMMAND_SEQ" ]]; then
#     local return_status=$?
#     # Log the command using recent2's log function
#     # Ensure log-recent is in your PATH
#     if command -v log-recent &>/dev/null; then
#       log-recent --shell zsh \
#                  -r "$return_status" \
#                  -p "$$" \
#                  --raw_command_text "$_RECENT2_CURRENT_COMMAND_TEXT" \
#                  --sequence_num "$_RECENT2_CURRENT_COMMAND_SEQ"
#     else
#       # Print a warning if log-recent is not found, but only once per session perhaps
#       if [[ -z "$_RECENT2_LOG_RECENT_WARNING_SHOWN" ]]; then
#         echo "recent2: log-recent command not found. Please ensure it's in your PATH." >&2
#         _RECENT2_LOG_RECENT_WARNING_SHOWN=1
#       fi
#     fi
#
#     # Unset the global variables to prevent re-logging or issues
#     unset _RECENT2_CURRENT_COMMAND_TEXT
#     unset _RECENT2_CURRENT_COMMAND_SEQ
#   fi
# }
#
# # Add the functions to their respective hooks
# # Ensure this is done only once to avoid duplicate entries if .zshrc is sourced multiple times
# if [[ -z "${precmd_functions[(r)_recent2_precmd]}" ]]; then
#   add-zsh-hook precmd _recent2_precmd
# fi
#
# if [[ -z "${preexec_functions[(r)_recent2_preexec]}" ]]; then
#   add-zsh-hook preexec _recent2_preexec
# fi
#
# # End of recent2 zsh setup
#
# # You can also put the functions directly in your .zshrc if you prefer,
# # instead of sourcing this file.
# # Make sure recent2 is installed (pip install recent2) and log-recent is in your PATH.
#
# # Example of adding directly to .zshrc:
# #
# # autoload -U add-zsh-hook # Make sure this is near the top if not already present
# #
# # _recent2_preexec() { ... function body from above ... }
# # _recent2_precmd() { ... function body from above ... }
# #
# # if [[ -z "${precmd_functions[(r)_recent2_precmd]}" ]]; then
# #   add-zsh-hook precmd _recent2_precmd
# # fi
# # if [[ -z "${preexec_functions[(r)_recent2_preexec]}" ]]; then
# #   add-zsh-hook preexec _recent2_preexec
# # fi
#
#
# # Notes on zsh history and sequence numbers:
# # HISTCMD variable in zsh contains the history line number of the current command.
# # This seems to be the most reliable way to get a sequence number that aligns with
# # how zsh numbers history entries.
# #
# # The command text is captured from the 3rd argument to preexec_functions ($3),
# # which zsh documentation states is the "full text that is being executed".
# #
# # `add-zsh-hook` is a helper function that safely adds a function to a hook array,
# # avoiding duplicates. It requires `autoload -U add-zsh-hook`.
#
# # Ensure PWD is correctly reported
# # By default, zsh's PWD should be fine. The log-recent script already captures PWD
# # using os.getenv('PWD', '').
#
# # To use, source this file in your .zshrc:
# # source /path/to/recent2_zsh_setup.sh
# # Or copy the relevant parts directly into your .zshrc.

# Make the script executable if someone tries to run it, though it's meant to be sourced or copied.
if [ "$0" = "${BASH_SOURCE[0]}" ]; then
    echo "This script is intended to be sourced by your .zshrc, or its contents copied into it."
    echo "Example: source $0"
    echo "Or, copy the function definitions and add-zsh-hook calls into your ~/.zshrc."
fi
