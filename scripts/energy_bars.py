"""Print the motion-energy curves of the replayed reference and of the new video side by side, frame by frame, as
text bars, for a range of frames. Fastest way to see WHERE a scene differs (a move missing, early, too slow, a fake
pause) before looking at the images.

Usage: python3 energy_bars.py out/compare/reference_recalee.mp4 out/film_silent.mp4 f0 f1 [--holes]
--holes: also list frames whose energy drops to ~0 between two moving frames in each video: in the REFERENCE they
mean duplicated frames (25 -> 30 i/s conversion, rule 52) or a replay problem; in the NEW video, a stall to fix.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def holes(E):
    nb = np.minimum(np.r_[E[1:], 0], np.r_[0, E[:-1]])
    return list(np.where((E < 0.15 * nb) & (nb > E.max() * 0.05))[0])


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    R = np.array(mk.curves(a[1])['energy']); N = np.array(mk.curves(a[2])['energy']); f0, f1 = int(a[3]), int(a[4])
    f1 = min(f1, len(R) - 1, len(N) - 1); sc = max(R[f0:f1 + 1].max(), N[f0:f1 + 1].max(), 1e-9) / 40
    print('image  référence rejouée                         | nouvelle vidéo')
    for f in range(f0, f1 + 1):
        print(f'{f:5d}  {"#" * int(R[f] / sc):<42s}| {"#" * int(N[f] / sc)}')
    if '--holes' in a:
        print('trous référence :', holes(R)); print('trous nouvelle  :', holes(N))


if __name__ == '__main__':
    main()
