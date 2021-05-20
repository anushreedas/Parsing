# Parsing
This repository provides parsing algorithms for several types of oracles on the provided CROHME training set.

1. Left-Right-Oracles:
These oracles sort symbols left-right by minimum x-coordinate, and then define a right relationship between all symbols (n−1edges).
(a)  Stroke oracle: treats every stroke as a symbol, classified according to the symbol it belongs to in ground truth.
(b)  Symbol oracle: correctly segments and classifies all symbols as given in ground truth.

2. Spanning Tree Oracles:
These oracles construct a minimum spanning tree over symbols,and then classify relationships as given in ground truth. The distance between two symbols given by the minimum distance between any pair of coordinates in the strokes between two symbols.
(a)  Stroke oracle: where every stroke is treated as a symbol with the class given in ground truth. After constructing a minimum spanning tree over symbols, classify spanning tree edges as given in ground truth (Note:no relationship is represented by ‘_’ (underscore)).
(b)  Symbol oracle: that constructs a minimum spanning tree over symbols from ground truth, For each spanning tree edge between symbols, assign the relationship given in ground truth (including no relationship (‘_’) if no relationship exists).