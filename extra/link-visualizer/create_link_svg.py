"""Visualize rssi links in an svg file."""

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)

path_here: Path = Path(__file__).parent
file_in_svg: Path = path_here / "floorplan.svg"
file_in_tb_log: Path = path_here / "trx_data.log"
path_output: Path = path_here
draw_nodes: bool = True

# -------------------------------------------------------

# node locations in pixel
NODES: Mapping[int, tuple[int, int]] = {
    1: (104, 110),
    2: (207, 70),
    3: (326, 31),
    4: (326, 99),
    5: (548, 69),
    6: (669, 85),
    7: (745, 177),
    8: (620, 363),
    # 9: (489, 320),
    10: (372, 395),
    11: (197, 337),
    12: (486, 375),
    13: (640, 180),
    14: (662, 225),
}

# -------------------------------------------------------


def indent(s: str, pre: str = "\t", *, empty: bool = False) -> str:
    if empty:
        indent1 = lambda l: pre + l
    else:
        indent1 = lambda l: l if s.isspace() else pre + l
    return "\n".join(map(indent1, s.split("\n")))


class SVGNodes:
    def __init__(self, color: str = "#FFFFFF") -> None:
        self.color: str = color
        self._nodes: list[str] = []

    @staticmethod
    def _gen_node(node: int, fill: str) -> str:
        x, y = NODES[node]
        return (
            f'<circle cx="{x}" cy="{y}" r="15" style="fill:{fill}"/>\n'
            f'<text transform="translate({x},{y})" dy=".36em" style="stroke:none">{node}</text>'
        )

    def add_node(self, node: int) -> None:
        self._nodes.append(self._gen_node(node, self.color))

    def get_svg_group(self) -> str:
        frame = (
            '<g style="fill:#000000;stroke:#000000;stroke-width:1;'
            'font:bold 17px sans-serif;text-anchor:middle">\n',
            "\n</g>\n",
        )
        data: str = "\n".join(self._nodes)
        return indent(data).join(frame)


class SVGLines:
    def __init__(self, color: str = "#000000", width: int = 1) -> None:
        self.color: str = color
        self.width: int = width
        self._lines: list = []

    @staticmethod
    def _gen_line(node1: int, node2: int, width: int) -> str:
        x1, y1 = NODES[node1]
        x2, y2 = NODES[node2]
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" style="stroke-width:{int(width)}"/>'

    def add_line(self, node1: int, node2: int, width: Optional[int] = None) -> None:
        self._lines.append(self._gen_line(node1, node2, self.width if width is None else width))

    def get_svg_group(self) -> str:
        frame = (f'<g style="stroke:{self.color}">\n', "\n</g>\n")
        data: str = "\n".join(self._lines)
        return indent(data).join(frame)


def update_svg(group, path_inp: Path, path_out: Path) -> None:
    with path_inp.open() as file:
        lines = file.readlines()
    k: int = 0
    i: int = 0
    for type_val in ("<svg", "<image"):
        while i < len(lines):
            if lines[i].strip().startswith(type_val):
                k = i + 1
                break
            i += 1
    lines.insert(k, group)
    logging.info("update file %s and save it to %s", path_inp, path_out)
    with path_out.open("w") as file:
        file.writelines(lines)


# -------------------------------------------------------


def line_width(x_val: float) -> int:
    y_val = (100 + x_val + 4) // 5
    if x_val and not y_val:
        logging.warning("rssi of %s converted to line_width 1", x_val)
        return 1
    if y_val > 10:
        logging.warning("rssi of %s converted to line_width 10", x_val)
        y_val = 10
    return round(y_val)


def tpl_line_width(tpl) -> int:
    if abs(tpl[0] - tpl[1]) > 6:
        logging.warning("received and sent signal strength differ a lot: %s", tpl)
    return line_width(sum(tpl) // 2)


def add_nodes(path_inp: Path, path_out: Path) -> None:
    svgn = SVGNodes(color="#FFFF00")
    for n in NODES:
        svgn.add_node(n)
    update_svg("\n" + svgn.get_svg_group(), path_inp, path_out)


def add_links(path_inp: Path, path_out: Path, rssi: dict) -> None:
    svgl = SVGLines(color="#0000FF")
    rssi_tpls = {}
    for (n1, n2), v in rssi.items():
        tpl = rssi_tpls.setdefault((min(n1, n2), max(n1, n2)), [v - 10, v - 10])
        tpl[n2 > n1] = v
    for (n1, n2), tpl in rssi_tpls.items():
        svgl.add_line(n1, n2, tpl_line_width(tpl))
    update_svg("\n" + svgl.get_svg_group(), path_inp, path_out)


# -------------------------------------------------------


def extract_rssi_data(file_path: Path) -> dict:
    data: list = []
    reading: bool = False
    with file_path.open() as file:
        for line in file.readlines():
            if reading:
                if line.isspace():
                    break
                data.append(line)
            elif "link matrix:" in line.lower():
                reading = True
    logging.info("link matrix:\n%s", "".join(data))
    # extract numbers
    head = [(int(m[1]), m.span()) for m in re.finditer(r"\s+(\d+)", data[0])]
    assert len(head) == len(data) - 2
    rssi: dict = {}
    for line in data[2:]:
        m = re.match(r"^\s*(\d+)\s*\|", line)
        n1 = int(m[1])
        offset = m.span()[1]
        for n2, (a, b) in head:
            v = line[max(a, offset) : b].strip()
            if v:
                rssi[(n1, n2)] = float(v)
    return rssi


if __name__ == "__main__":
    if not file_in_svg.exists():
        FileNotFoundError("base SVG-File needed")
    if path_output.exists():
        FileExistsError("Output-File already exists")
    if path_output.is_dir():
        path_output = path_output / (file_in_svg.stem + "_linked" + file_in_svg.suffix)

    if draw_nodes:
        logging.info("add nodes")
        add_nodes(file_in_svg, path_output)
        file_in_svg = path_output

    if file_in_tb_log.exists():
        rssi_dic = extract_rssi_data(file_in_tb_log)
        add_links(file_in_svg, path_output, rssi_dic)
    else:
        logging.warning("no TrafficBench data defined")

    logging.info("svg file %s created", path_output.name)
