
import re

from lex.oed.thesaurus.dbbackend.subjectmapper import SubjectMapper

from utils.tracer import trace_sense, trace_instance, trace_class
from .definitiontogloss import definition_to_gloss
from .nounphraser import NounPhraser
from .branchdeducer import BranchDeducer
from .locatesynonyms import locate_synonyms
from .viabilitytester import is_viable

BRANCH_DEDUCER = BranchDeducer()
SUBJECT_MAPPER = SubjectMapper()
LEMMA_TOKENIZER = (re.compile(r"^([a-z-]+) (of| of the) ([a-z-]+)$", re.I),
                   re.compile(r"^([^' ]+)('s |'s-|' |-| )([a-z-]+)$", re.I),)
IRREGULAR_PPLES = {'built', 'held', 'born', 'worn', 'torn'}


class SenseObject(object):

    def __init__(self, entry, sense, position_in_entry, total_senses,
                 clone_num, label_parser):
        self.lemma = sense.lemma
        self.thesaurus = sense.thesaurus_categories()
        self.entry_id = int(entry.id)
        self.node_id = int(sense.node_id())
        self.entry_lemma = entry.lemma
        self.wordclass = sense.primary_wordclass().penn
        self.is_subentry = sense.is_subentry()
        self.subentry_type = sense.subentry_type() or 'main sense'
        self.num_lemmas = len(sense.internal_lemmas())
        self.definition = sense.definition(length=200) or None
        self.headers = sense.header_strings()
        self.position_in_entry = position_in_entry
        self.senses_in_entry = total_senses

        self.gloss = definition_to_gloss(sense.definition_manager().serialized(), self.wordclass)
        if not self.gloss and sense.parent_definition_manager() is not None:
            self.gloss = definition_to_gloss(
                sense.parent_definition_manager().serialized(), self.wordclass)

        # Version number for this copy of the sense. Will usually be 0;
        #  clone_nums #1, #2, etc., will only occur where the dictionary
        #  sense has multiple subdefs that have been cloned to produce
        #  separate sense objects.
        self.clone_num = clone_num

        # Taxonomic stuff
        self.genera = (sense.definition_manager().genera() or
                       sense.definition_manager().families())
        self.binomials = sense.definition_manager().binomials()
        self.quotations_binomials = sense.quotations_binomials()

        # List of subject labels for this sense, omitting any that are
        #  not salient for thesaurus classification
        self.subjects = set()
        for label in sense.labels():
            for node in label_parser.map_label_to_nodes(label):
                if SUBJECT_MAPPER.is_thesaurus_mapped(node):
                    self.subjects.add(node)
                    break

        # List of thesaurus branches corresponding to any cross-references
        #  in the sense
        self.cross_references = [Xref(xr) for xr in
                                 sense.definition_manager().cross_references()
                                 if xr.target_type() != 'quotation' and
                                 xr.refentry() is not None and
                                 xr.refid() is not None]

        # Etyma
        if sense.is_subentry() or sense.is_subentry_like():
            self.etyma = []
        else:
            etyma = [et for et in entry.etymology().etyma() if
                     et.type() == 'cross-reference']
            self.etyma = [(et.lemma, et.refentry(), et.refid()) for et in etyma]

        if (self.wordclass is None and
                (self.subentry_type == 'phrase' or
                sense.primary_wordclass().source == 'phrase')):
            self.wordclass = 'PHRASE'

        # Synonyms
        self.synonyms = locate_synonyms(self)

        np = NounPhraser(self)
        self.superordinate_full, self.superordinate, self.superordinate_tail = np.superordinate()
        self.noun_phrases_full = [n.full for n in np.noun_phrases()]
        self.noun_phrases = [n.short for n in np.noun_phrases()]

        # Likely thesaurus branches, based on evaluating any unambiguous
        #   cross-references
        self.xref_branches = BRANCH_DEDUCER.branches_from_xrefs(self)

        # The following will only be invoked when processing senses which
        #   have already been classified; otherwise, self.thesaurus_nodes
        #   will be left undefined.
        if sense.thesaurus_categories():
            self.thesaurus_nodes = [int(n) for n in sense.thesaurus_nodes()]

        # Keep an inventory of all the attributes that the object has when
        #  it's initialized - so that we can later strip off any extraneous
        #  attributes.
        # Make sure the inventory itself is included!
        self.inventory = tuple(list(self.__dict__.keys()) + ['inventory', ])

    def equals_crossreference(self):
        xrefs = [xr for xr in self.cross_references if xr.type == 'equals']
        if xrefs:
            return xrefs[0]
        else:
            return None

    def cf_crossreference(self):
        xrefs = [xr for xr in self.cross_references if xr.type == 'cf']
        if xrefs:
            return xrefs[0]
        else:
            return None

    def strip_attributes(self):
        """
        Remove extraneous attributes from the sense's __dict__
        """
        original_attributes = set(self.inventory)
        keys = list(self.__dict__.keys())
        for att in keys:
            if att not in original_attributes:
                del(self.__dict__[att])

    #================================================
    # First and last elements of a compound lemma
    #================================================

    def last_element(self):
        try:
            return self._last_element
        except AttributeError:
            self._tokenize_lemma()
            return self._last_element

    def last_word(self):
        return self.last_element()

    def first_element(self):
        try:
            return self._first_element
        except AttributeError:
            self._tokenize_lemma()
            return self._first_element

    def first_word(self):
        return self.first_element()

    def _tokenize_lemma(self):
        m1 = LEMMA_TOKENIZER[0].search(self.lemma)
        m2 = LEMMA_TOKENIZER[1].search(self.lemma)
        w1, w2 = (None, None)
        if m1 is not None:
            # 'x of y'-type compounds: we reverse the order of the words,
            #  since 'admiral of the fleet' is like 'fleet admiral'
            w1 = m1.group(3)
            w2 = m1.group(1)
        elif m2 is not None:
            # ... whereas these are regular 'x-y'-type compounds, so we keep
            #  the words in their regular order
            w1 = m2.group(1)
            w2 = m2.group(3)
        elif (self.subentry_type == 'compound' and
                self.lemma.startswith(self.entry_lemma)):
            w1 = self.entry_lemma
            w2 = self.lemma.replace(self.entry_lemma, '').strip(' -')
            w2 = re.sub(r"^'s[ -]*", '', w2)
        elif (self.subentry_type == 'main sense' and
                len(self.etyma) == 2 and
                self.lemma.lower() == ''.join([e[0] for e in self.etyma]).lower()):
            w1 = self.etyma[0][0]
            w2 = self.etyma[1][0]

        # Affix entries
        if w1 is None and self.subentry_type == 'affix':
            prefix = self.entry_lemma.strip('-')
            if (self.lemma.startswith(prefix) and
                    len(self.lemma) > len(prefix) + 3):
                w1 = prefix
                w2 = self.lemma[len(prefix):]

        # Try again with the etyma, allowing a bit more flexibility in
        #  how they're combined to produce the lemma
        if (w1 is None and self.subentry_type == 'main sense' and
                self.lemma.lower() == self.entry_lemma.lower() and
                len(self.etyma) == 2):
            et1 = self.etyma[0][0]
            et2 = self.etyma[1][0]
            if (et1.startswith('-') or
                    et1.endswith('-') or
                    et2.startswith('-') or
                    et2.endswith('-')):
                # Skip if either is an affix
                pass
            elif et1.lower()[0:4] == et2.lower()[0:4]:
                # Skip if the two etyma are actually two versions
                #  of the same words
                pass
            else:
                et1_short = et1.lower()[0:4]
                et2_short = et2.lower()[-4:]
                if (self.lemma.lower().startswith(et1_short) and
                        self.lemma.lower().endswith(et2_short)):
                    w1 = et1
                    w2 = et2

        self._first_element = w1
        self._last_element = w2

    def is_parasynthetic(self):
        for h in self.headers:
            if 'parasynthetic' in h.lower():
                return True
        return False

    def is_possibly_parasynthetic(self):
        if self.is_parasynthetic():
            return True
        elif self.last_element() is None:
            return False
        elif (self.wordclass == 'JJ' and
                (self.last_element() in IRREGULAR_PPLES or
                re.search(r'(ing|[^ae]ed|[^aeiou]en)$', self.last_element()) )):
            return True
        else:
            return False

    def is_intractable(self):
        if is_viable(self):
            return False
        else:
            return True

    def is_affix(self):
        if self.lemma.startswith('-') or self.lemma.endswith('-'):
            return True
        else:
            return False

    def is_affix_subentry(self):
        if self.subentry_type == 'affix':
            return True
        # This clause shouldn't be necessary; just added as a safety measure
        elif self.is_subentry and self.entry_lemma.endswith('-'):
            return True
        else:
            return False

    def is_first(self):
        if self.position_in_entry == 0:
            return True
        else:
            return False

    def is_only_sense(self):
        if self.position_in_entry == 0 and self.senses_in_entry == 1:
            return True
        else:
            return False

    def is_undefined(self):
        if self.definition is None or not self.definition:
            return True
        if self.gloss is None or not self.gloss:
            return True
        else:
            return False

    def is_split_definition(self):
        if self.clone_num > 0:
            return True
        else:
            return False

    def oed_url(self):
        return 'http://www.oed.com/view/Entry/%d#eid%d' % (self.entry_id,
                                                           self.node_id)

    def subject_classes(self):
        try:
            return self._subject_classes
        except AttributeError:
            self._subject_classes = []
            for topic in self.subjects:
                self._subject_classes.extend(SUBJECT_MAPPER.equivalent_classes(topic))
            self._subject_classes = [t for t in self._subject_classes
                                     if t is not None]
            return self._subject_classes


class BayesManager(object):

    """
    Wrapper for storing and managing the various Bayes classifications
    associated with this sense
    """

    def __init__(self):
        self._result_objects = {}

    def insert(self, mode, result_obj):
        if result_obj is not None and result_obj:
            result_obj.recover_probabilities()
        self._result_objects[mode] = result_obj

    def result_object(self, **kwargs):
        """
        Return the Bayes result object for this sense.

        Keyword arguments:
         * mode: defaults to 'main'
        """
        mode = kwargs.get('mode', 'main')
        try:
            return self._result_objects[mode]
        except (AttributeError, KeyError):
            return None

    def confidence(self, **kwargs):
        """
        Return confidence rating associated with the Bayes result object
        for this sense. The confidence rating is an integer between 0 and 10

        Keyword arguments:
         * mode: defaults to 'main'
        """
        if self.result_object(**kwargs) is None:
            return 0
        else:
            return self.result_object(**kwargs).confidence()

    def is_usable(self, **kwargs):
        """
        Return True or False, depending on whether or not the Bayes
        result object for this sense is considered usable (i.e. is not
        None and has a confidence rating > 1).

        Keyword arguments:
         * mode: defaults to 'main'
        """
        if self.confidence(**kwargs) > 1:
            return True
        else:
            return False

    def filtered_results(self, **kwargs):
        if self.result_object(**kwargs) is None:
            return []
        else:
            return self.result_object(**kwargs).filtered_results(**kwargs)

    def ids(self, **kwargs):
        """
        Return the ranked list of thesaurus class IDs from the Bayes result
        object for this sense.

        Keyword arguments:
         * mode: defaults to 'main'
        """
        return [r.id for r in self.filtered_results(**kwargs)]

    def branches(self, **kwargs):
        """
        Return the ranked list of thesaurus branches from the Bayes result
        object for this sense.

        Keyword arguments:
         * mode: defaults to 'main'
        """
        return [r.thesclass() for r in self.filtered_results(**kwargs)]

    def ancestors(self, **kwargs):
        """
        Return a set of ancestor thesaurus branches from the Bayes result
        object for this sense.

        The ancestor level can be specified with the 'level' keyword argument.

        Keyword arguments:
         * mode: defaults to 'main'
         * level: ancestor level; defaults to '2'
        """
        lev = kwargs.get('level', 2)
        ancestors = [b.ancestor(level=lev) for b in self.branches(**kwargs)]
        return set([a for a in ancestors if a is not None])


class Xref(object):

    def __init__(self, xr):
        self.lemma = xr.lemma()
        self.refentry = xr.refentry()
        self.refid = xr.refid()
        self.target_type = xr.target_type()
        self.type = xr.type

    def __repr__(self):
        if self.lemma is not None and self.type is not None:
            return '<Xref %s %d#eid%d (%s)>' % (self.lemma, self.refentry,
                                                self.refid, self.type)
        elif self.lemma is not None:
            return '<Xref %s %d#eid%d>' % (self.lemma, self.refentry,
                                           self.refid)
        elif self.type is not None:
            return '<Xref %d#eid%d (%s)>' % (self.refentry, self.refid,
                                             self.type)
        else:
            return '<Xref %d#eid%d>' % (self.refentry, self.refid)
