from minilang import run


def output(source):
    """What a program prints, as a list of lines."""
    lines = []
    run(source, lines.append)
    return lines


def value(expression):
    """What an expression prints."""
    return output(f"print({expression});")[0]
