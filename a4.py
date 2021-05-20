"""
This program implements 4 parsing systems for the strokes to get symbols
and stores the output.
The 4 systems are:
1. left-right stroke oracle
2. left-right symbol oracle
3. spanning-tree stroke oracle
4. spanning-tree symbol oracle

@author: Anushree Das
"""
import sys
import xml.etree.ElementTree as ET
from random import randrange
import os
import operator
from tqdm import tqdm
import numpy as np
from scipy.spatial import distance
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import minimum_spanning_tree


class Expression:
    def __init__(self, files):
        self.filename = files[0]
        self.gt_file = files[1]
        self.strokes = self.get_strokes()
        self.symbols_gt = []
        self.relationships_gt = []
        self.symbols = []
        self.relationships = []

    def get_strokes(self):
        try:
            tree = ET.parse(self.filename, ET.XMLParser(encoding='utf-8'))
        except Exception:
            try:
                tree = ET.parse(self.filename, ET.XMLParser(encoding='iso-8859-1'))
            except Exception:
                return []
        root = tree.getroot()
        doc_namespace = "{http://www.w3.org/2003/InkML}"

        strokes = dict()
        # extract stroke info
        for trace_tag in root.findall(doc_namespace + 'trace'):
            coods = [[round(float(axis_coord))
                      if float(axis_coord).is_integer()
                      else round(float(axis_coord) * 10000)
                      for axis_coord in coord[1:].split(' ')[:2]]
                     if coord.startswith(' ')
                     else [round(float(axis_coord))
                           if float(axis_coord).is_integer()
                           else round(float(axis_coord) * 10000)
                           for axis_coord in coord.split(' ')]
                     for coord in (trace_tag.text).replace('\n', '').split(',')]
            # extract only x and y coordinates
            strokes[trace_tag.get('id')]=[[row[0],row[1]] for row in coods]

        return strokes

    def set_gt(self):
        try:
            tree = ET.parse(self.filename, ET.XMLParser(encoding='utf-8'))
        except Exception:
            try:
                tree = ET.parse(self.filename, ET.XMLParser(encoding='iso-8859-1'))
            except:
                return
        root = tree.getroot()
        doc_namespace = "{http://www.w3.org/2003/InkML}"

        # Always 1st traceGroup is a redundant wrapper'
        traceGroupWrapper = root.find(doc_namespace + 'traceGroup')
        symbols = []

        if traceGroupWrapper is not None:
            # Process each symbol
            for traceGroup in traceGroupWrapper.findall(doc_namespace + 'traceGroup'):
                # get symbol class and id
                symbol_class = traceGroup.find(doc_namespace + 'annotation').text
                symbol_class = symbol_class.replace(',', 'COMMA')
                sym_id_ann = traceGroup.find(doc_namespace + 'annotationXML')

                if sym_id_ann is not None:
                    sym_id = sym_id_ann.get('href')
                    sym_id = sym_id.replace(',', 'COMMA')
                else:
                    sym_id = symbol_class + '_' + str(randrange(100))

                # get stroke ids
                strokeid_list = []
                for traceView in traceGroup.findall(doc_namespace + 'traceView'):
                    stroke_id = traceView.get('traceDataRef')
                    strokeid_list.append(stroke_id)
                # create Symbol object to store all symbol segmentations ground truth extracted from the inkml file
                symbols.append(Symbol(sym_id, symbol_class, strokeid_list))

        self.symbols_gt = symbols

        # get relationships ground truth from lg file
        relationships = []
        with open(self.gt_file,'r') as f:
            rows = f.readlines()
            for row in rows:
                cols = row.split(',')
                if cols[0] == 'R':
                    # create Relationship object to store all relationship ground truth extracted from the lg file
                    relationships.append(Relationship(cols[1].strip(),cols[2].strip(),cols[3].strip()))
        self.relationships_gt = relationships

    def add_relation(self,i,j):
        # classify relationship as given in ground truth
        found = False
        for rel in self.relationships_gt:

            if self.symbols[i].symbol_id_og == rel.symbol_id_1 and self.symbols[j].symbol_id_og == rel.symbol_id_2:
                self.relationships.append(Relationship(self.symbols[i].symbol_id,
                                                       self.symbols[j].symbol_id, rel.symbol_relation))
                found = True
                break
            elif self.symbols[i].symbol_id_og == rel.symbol_id_2 and self.symbols[j].symbol_id_og == rel.symbol_id_1:
                self.relationships.append(Relationship(self.symbols[j].symbol_id,
                                                       self.symbols[i].symbol_id, rel.symbol_relation))
                found = True
                break

        # if relationship not given in ground truth, label relaship as '_'
        if not found:
            self.relationships.append(Relationship(self.symbols[i].symbol_id,
                                                   self.symbols[j].symbol_id, '_'))

    def stroke_oracle(self):
        # get ground truth
        self.set_gt()

        stroke_ids_all = list(self.strokes.keys())

        # create separate Symbol object for each stroke id for each symbol in ground truth
        if self.symbols_gt:
            for symbol in self.symbols_gt:
                for l in range(len(symbol.stroke_list)):
                    stroke_id = symbol.stroke_list[l]
                    sym = Symbol(symbol.symbol_id+'_'+str(l), symbol.symbol_class, [stroke_id])
                    # set original symbol id for reference to use while
                    # comparing relationships in ground truth to classify them
                    sym.set_id_gt(symbol.symbol_id)
                    self.symbols.append(sym)
                    stroke_ids_all.remove(stroke_id)

        symbol_id = 1
        # create separate Symbol object for each stroke id which doesn't belong to any symbol
        for stroke_id in stroke_ids_all:
            sym = Symbol('ABSENT_' + str(symbol_id), 'ABSENT', [stroke_id])
            sym.set_id_gt('ABSENT_' + str(symbol_id))
            self.symbols.append(sym)
            symbol_id += 1

    def symbol_oracle(self):
        stroke_ids_all = list(self.strokes.keys())

        # get ground truth
        self.set_gt()

        # create Symbol object for each symbol in ground truth
        if self.symbols_gt:
            for symbol in self.symbols_gt:
                for stroke_id in symbol.stroke_list:
                    stroke_ids_all.remove(stroke_id)
                sym = Symbol(symbol.symbol_id, symbol.symbol_class, symbol.stroke_list)
                # set original symbol id for reference to use while
                # comparing relationships in ground truth to classify them
                sym.set_id_gt(symbol.symbol_id)
                self.symbols.append(sym)

        symbol_id = 1
        # create separate Symbol object for each stroke id which doesn't belong to any symbol
        for stroke_id in stroke_ids_all:
            sym = Symbol('ABSENT_' + str(symbol_id), 'ABSENT', [stroke_id])
            sym.set_id_gt('ABSENT_' + str(symbol_id))
            self.symbols.append(sym)
            symbol_id += 1

    def left_right_oracle(self):
        # find minimum x-coordinate for each symbol
        for symbol in self.symbols:
            x_coords = []
            for stroke_id in symbol.stroke_list:
                x_coords.extend([x for x, y in self.strokes[stroke_id]])
            min_x = min(x_coords)
            symbol.set_min(min_x)

        #  sort symbols left-right by minimum x-coordinate
        self.symbols = sorted(self.symbols, key=operator.attrgetter("min_x"))

        # add relationship between adjacent symbols in the sorted list(n-1 edges)
        for i in range(1,len(self.symbols)):
            self.add_relation(i-1, i)

    def lr_stroke_oracle(self):

        if len(self.strokes) != 0:
            # reset arrays
            self.symbols = []
            self.relationships = []

            # treat every stroke as a symbol
            self.stroke_oracle()

            # add relationship between symbols based on their min x coordinate
            self.left_right_oracle()

        # write all output symbols created to .lg file
        self.write_lgfile('lr_stroke_oracle')

    def lr_symbol_oracle(self):

        if len(self.strokes) != 0:
            # reset arrays
            self.symbols = []
            self.relationships = []

            # correctly segments and classifies all symbols
            self.symbol_oracle()

            # add relationship between symbols based on their min x coordinate
            self.left_right_oracle()

        # write all output symbols created to .lg file
        self.write_lgfile('lr_symbol_oracle')

    def find_min(self,list1,list2):
        # Returns minimum distance between all coordinates of two clusters
        return min(distance.cdist(list1,list2).min(axis=1))

    def min_spanning_tree(self):
        # store coordinates for each symbol(all strokes) for easier distance calculation
        coods = []
        for symbol in self.symbols:
            single_cluster_coods = []
            for stroke_id in symbol.stroke_list:
                single_cluster_coods.extend(self.strokes[stroke_id])
            coods.append(single_cluster_coods)

        # initialize distance matrix
        dist = [[np.Inf for _ in range(len(self.symbols))] for _ in range(len(self.symbols))]

        # get minimum distance between two clusters
        for i in range(len(self.symbols) - 1):
            for j in range(i + 1, len(self.symbols)):
                dist[i][j] = self.find_min(coods[i], coods[j])

        X = csr_matrix(dist)
        # build minimum spanning tree
        Tcsr = minimum_spanning_tree(X)
        span_tree = Tcsr.toarray()

        # add relationship between symbols based on spanning tree edges
        for i in range(len(self.symbols) - 1):
            for j in range(i + 1, len(self.symbols)):
                if span_tree[i][j] != 0:
                    self.add_relation(i, j)

    def mst_stroke_oracle(self):
        if len(self.strokes) != 0:
            # reset arrays
            self.symbols = []
            self.relationships = []

            # treat every stroke as a symbol
            self.stroke_oracle()

            # add relationship between symbols based on min spanning tree edges
            self.min_spanning_tree()

        # write all output symbols created to .lg file
        self.write_lgfile('mst_stroke_oracle')

    def mst_symbol_oracle(self):
        if len(self.strokes) != 0:
            # reset arrays
            self.symbols = []
            self.relationships = []

            # correctly segments and classifies all symbols
            self.symbol_oracle()

            # add relationship between symbols based on min spanning tree edges
            self.min_spanning_tree()

        # write all output symbols created to .lg file
        self.write_lgfile('mst_symbol_oracle')

    def write_lgfile(self, directory):
        # writes the output to .lg file

        if not os.path.exists(directory):
            os.makedirs(directory)
        filepath = os.path.join(directory, os.path.splitext(os.path.basename(self.filename))[0] + '.lg')
        with open(filepath, 'w') as f:
            for symbol in self.symbols:
                f.write('O, ' + str(symbol.symbol_id) + ', ' + symbol.symbol_class + ', 1.0')
                for stroke_id in symbol.stroke_list:
                    f.write(', ' + str(stroke_id))
                f.write('\n')
            for relationship in self.relationships:
                f.write('R, '+relationship.symbol_id_1+', '+str(relationship.symbol_id_2)+', '+relationship.symbol_relation+', 1.0')
                f.write('\n')


# data structure to store symbol information
class Symbol:
    def __init__(self,sym_id,sym_class,stroke_l):
        self.symbol_id = sym_id
        self.symbol_class = sym_class
        self.stroke_list = stroke_l

    def set_min(self,x):
        self.min_x = x

    def set_id_gt(self,sym_id):
        self.symbol_id_og = sym_id


# data structure to store relationship information
class Relationship:
    def __init__(self,sym_id_1,sym_id_2,sym_relation):
        self.symbol_id_1 = sym_id_1
        self.symbol_id_2 = sym_id_2
        self.symbol_relation = sym_relation


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: python3 a4.py [path to inkml directory] [path to lg directory] [lr_stroke|lr_symbol|mst_stroke|mst_symbol]')
        exit(0)
    inkml_path = sys.argv[1]
    lg_path = sys.argv[2]
    segmenter = sys.argv[3]

    if not os.path.exists(inkml_path):
        print("Path doesn't exist")
        exit(0)
    if not os.path.exists(lg_path):
        print("Path doesn't exist")
        exit(0)

    segmenters = ['lr_stroke', 'lr_symbol', 'mst_stroke', 'mst_symbol']
    if segmenter not in segmenters:
        print('Incorrect parameter value: ', segmenter)
        print('Usage: python3 a4.py [path to inkml directory] [path to lg directory] [lr_stroke|lr_symbol|mst_stroke|mst_symbol]')
        exit(0)

    lg_filelist = {}
    # get all inkml files from directory and sub-directories
    for root, dirs, files in os.walk(lg_path):
        for file in files:
            if os.path.splitext(file)[1] == '.lg':
                lg_filelist[os.path.splitext(os.path.basename(file))[0]]=os.path.join(root, file)

    filelist =[]
    # get all lg files from directory and sub-directories
    for root, dirs, files in os.walk(inkml_path):
        for file in files:
            if os.path.splitext(file)[1] == '.inkml':
                # if the corresponding lg file exists then add to filelist
                if lg_filelist[os.path.splitext(os.path.basename(file))[0]] is not None:
                    filelist.append([os.path.join(root, file),lg_filelist[os.path.splitext(os.path.basename(file))[0]]])

    for files in tqdm(filelist):
        e = Expression(files)
        if segmenter == 'lr_stroke':
            e.lr_stroke_oracle()
        elif segmenter == 'lr_symbol':
            e.lr_symbol_oracle()
        elif segmenter == 'mst_stroke':
            e.mst_stroke_oracle()
        elif segmenter == 'mst_symbol':
            e.mst_symbol_oracle()

