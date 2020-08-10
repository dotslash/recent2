set -euxo pipefail # Fail fast
# Dont print the commands bacause we run commnds in big for loop
set +o xtrace

# We will log metrics here. Later we will generate a plot from this.
LOG_FILE=/tmp/recent2_bench_$(uuidgen)
WRITE_BATCH_SIZE=500 # We write 3 batches of this size.
BASH_HISTORY_IMPORT_SIZE=200000 # We will import these many from history file
NUM_QUERIES_BY_2=500 # We will do 2*<this> number of queries.
NUM_ITERATIONS=3 # We will run the benchmark this many times.
FILE_DIR=$(dirname "$0")


function log() {
  local now
  now=$(date)
  echo "$now : $1"
}

function logAndWriteEvent() {
    local eventName=$1
    log "Event $eventName"
    local now
    now=$(date +%s)
    echo "$eventName $now" >> "$LOG_FILE"
}

function logCommandsToRecent() {
    local numCmds=$1
    for (( i = 0; i < numCmds; i++ )); do
        log-recent -r 0 -c " 11$i cmd $i" -p 4556
    done
}

function reset_cache() {
    vmtouch -v $1
    vmtouch -e $1
    log "Reset page cache for $1"
}

function benchiter() {
    # recent db location
    RECENT_DB="/tmp/recent2_bench_$(uuidgen).db"
    # recent import marker. recent2 will store a boolean here that
    # it imported bash history.
    RECENT_TEST_IMPORT_FILE="/tmp/recent2_bench_$(uuidgen).txt"
    # recent will import bash history from here
    HISTFILE="/tmp/recent2_bench_$(uuidgen).hist.txt"

    export RECENT_DB
    export RECENT_TEST_IMPORT_FILE
    export HISTFILE

    log "RECENT_DB -> $RECENT_DB"
    log "LOG_FILE -> $LOG_FILE"
    log "RECENT_TEST_IMPORT_FILE -> $RECENT_TEST_IMPORT_FILE"
    log "HISTFILE -> $HISTFILE"


    log-recent -r 0 -c " 1 command from different session" -p 4556

    log "Logging commands start"

    for li in {1..3} ; do
      reset_cache $RECENT_DB
      logAndWriteEvent "log.${WRITE_BATCH_SIZE}.batch${li} start"
      logCommandsToRecent $WRITE_BATCH_SIZE
      logAndWriteEvent "log.${WRITE_BATCH_SIZE}.batch${li} end"
    done

    log "Preparing bash history"
    python3 "$FILE_DIR/prepare_bash_history.py" "imported_cmd" "$BASH_HISTORY_IMPORT_SIZE" "$HISTFILE"

    log "Importing bash hisory"
    reset_cache $RECENT_DB
    logAndWriteEvent "import.${BASH_HISTORY_IMPORT_SIZE} start"
    recent-import-bash-history > /dev/null
    logAndWriteEvent "import.${BASH_HISTORY_IMPORT_SIZE} end"

    log "Querying bash history"
    NUM_QUERIES=$(expr $NUM_QUERIES_BY_2 + $NUM_QUERIES_BY_2)
    logAndWriteEvent "query.${NUM_QUERIES} start"
    reset_cache $RECENT_DB
    for (( i = 0; i < NUM_QUERIES_BY_2; i++ )); do
        recent "cmd $i" > /dev/null
        recent "imported ${i}00" > /dev/null
    done
    logAndWriteEvent "query.${NUM_QUERIES} end"

}

for (( iternum = 0; iternum < NUM_ITERATIONS; iternum++ )); do
  log ">>>>>>>>>>>>>>>>>>>>>>>> Starting iteration $iternum"
  benchiter
done

python3 "$FILE_DIR/print_metrics.py" "$LOG_FILE" "$FILE_DIR/results.txt"
cat "$FILE_DIR/results.txt"