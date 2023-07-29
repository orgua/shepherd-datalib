from pathlib import Path
from timeit import timeit

from shepherd_core.decoder_waveform import Uart

# file captured with logic analyzer, 15.5k events (2700 symbols, 61 lines)
trace = Path(__file__).parent / "uart_raw2.csv"
uwd = Uart(trace)

sym = uwd.get_symbols()
lne = uwd.get_lines()
txt = uwd.get_text()
# print(txt)

print("t_init=", timeit("Uart(trace)", globals=globals(), number=1000))
print("t_symb=", timeit("uwd.get_symbols(True)", globals=globals(), number=1000))
print("t_line=", timeit("uwd.get_lines(True)", globals=globals(), number=1000))
print("t_text=", timeit("uwd.get_text(True)", globals=globals(), number=1000))
# Results:
# t_init=  5.8 [ms/run]
# t_symb= 70.4  [!!!!!]
# t_line=  3.9
# t_text=  0.1