import pathlib
import sys

if __name__ == '__main__':
    prefix = sys.argv[1]
    num_lines = int(sys.argv[2])
    dest = sys.argv[3]

    about = "Write {} lines that start with {} at {}".format(num_lines, prefix, dest)
    print("Starting operation: " + about)
    lines = ['{} {}'.format(prefix, i) for i in range(num_lines)]
    text = '\n'.join(lines) + "\n"
    pathlib.Path(dest).expanduser().absolute().write_text(text)
    print("Done with operation: " + about)
