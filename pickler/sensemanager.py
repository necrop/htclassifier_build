import os
import string
import copy
import pickle

from lex.entryiterator import EntryIterator

from .senseobject import SenseObject
from .postagger import PosTagger
from resources.subjectlabelparser import SubjectLabelParser
from utils.tracer import trace_sense

letters = string.ascii_uppercase


class SensePickler(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def pickle_senses(self):
        # prime the pos-tagger
        PosTagger(dir=os.path.join(self.resources_dir, 'postagger'))
        # prime the subject-label parser
        self.label_parser = SubjectLabelParser(
            file=os.path.join(self.resources_dir, 'subject_ontology.xml'))

        for letter in letters:
            filter = 'oed_%s.xml' % letter
            if self.output_dir is not None:
                # Regular mode - with an output filehandle
                outfile = os.path.join(self.output_dir, letter)
                with open(outfile, 'wb') as self.filehandle:
                    self._process_entries(filter)
            else:
                # Test mode - no output filehandle
                self.filehandle = None
                self._process_entries(filter)

    def _process_entries(self, file_filter):
        iterator = EntryIterator(dictType='oed',
                                 fixLigatures=True,
                                 verbosity='low',
                                 fileFilter=file_filter)
        for entry in iterator.iterate():
            self.current_entry = entry
            for s1 in entry.s1blocks():
                s1.share_quotations()
                for i, s in enumerate(s1.senses()):
                    self._process_sense(s, i, len(s1.senses()))
            for s in entry.lemsect_senses():
                self._process_sense(s, 5, 10)
            for s in entry.revsect_senses():
                self._process_sense(s, 5, 10)

    def _process_sense(self, sense, position, num_senses):
        if sense.is_xref_sense():
            pass
        elif (not sense.is_subentry() and
                sense.is_in_lemsect() and
                not any([a.tag == 'sub' for a in sense.ancestor_nodes()])):
            pass
        elif ((self.mode == 'unclassified' and not sense.thesaurus_categories()) or
                (self.mode == 'classified' and sense.thesaurus_categories()) or
                self.mode == 'both'):
            # If an unclassified sense has multiple definitions, we split
            #   these out to form a series of separate senseObjects
            # These get marked with clone_num 1, 2, 3, etc., unlike the
            #   full sense which has clone_num = 0
            if self.mode in ('unclassified', 'both'):
                subdefs = sense.subdefinitions(split_text=True,
                                               allow_anaphora=False)
                for i, subdef in enumerate(subdefs):
                    sense_copy = copy.copy(sense)
                    # Splice in the subdef in place of the original
                    #  full definition
                    sense_copy.reset_definition(subdef)
                    self._dump_sense(sense_copy, position, num_senses, i+1)
            # We always store the full sense (as clone_num=0),
            #  irrespective of whether it has also been split into
            #  separate subdefinitions.
            self._dump_sense(sense, position, num_senses, 0)

    def _dump_sense(self, sense, position, num_senses, clone_num):
        sense_obj = SenseObject(self.current_entry, sense, position,
                                num_senses, clone_num, self.label_parser)
        if self.filehandle is not None:
            pickle.dump(sense_obj, self.filehandle)


class PickleLoader(object):
    """
    Iterator for loading and returning a series of SenseObjects
    from a sequence of pickled files
    """

    def __init__(self, dir, letters=None):
        if letters is not None:
            letters = letters.upper()
        self.dir = dir
        self.letters = letters

    def iterate(self):
        for letter in string.ascii_uppercase:
            if self.letters is None or letter in self.letters:
                f = os.path.join(self.dir, letter)
                if os.path.isfile(f):
                    with open(f, 'rb') as filehandle:
                        while 1:
                            try:
                                sense = pickle.load(filehandle)
                            except EOFError:
                                break
                            else:
                                yield sense
