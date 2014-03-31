import shutil
import os
import re
import string
from collections import defaultdict
import pickle

import lex.oed.thesaurus.thesaurusdb as tdb

from pickler.sensemanager import PickleLoader
from resources.binomials import Binomials
from resources.mainsense.mainsense import MainSense
from resources.derivationtester import DerivationTester
from resources.superordinates.superordinates import Superordinates
from bayes.bayesclassifier import BayesClassifier
from compounds.bayescompounds import BayesCompounds
from compounds.formalcompoundanalysis import FormalCompoundAnalysis
from compounds.indexer.rawindexer import CompoundIndexer
from pickler.senseobject import BayesManager
from .topicalclassifier import topical_classification
from .rankedsensesummary import ranked_sense_summary
from .bayesfilter import apply_bayes_filter
from . import synonymchecker

#from utils.tracer import trace_sense, trace_instance, trace_class

binomial_checker = Binomials()
superordinate_manager = Superordinates()
main_sense_finder = MainSense()
deriv_tester = DerivationTester()
formal_compound_analysis = FormalCompoundAnalysis()
triage = ('classified', 'unclassified', 'intractable')

letters = string.ascii_uppercase


class Classifier(object):

    def __init__(self, **kwargs):

        # Prime various classes with the kwargs values
        #  (so that they can subsequently be initialized from other points
        #  in the code without any arguments)
        # Prime the binomial checker
        Binomials(**kwargs).load_data()
        # Prime the main-sense finder
        MainSense(**kwargs).load_data()
        # Prime the derivation tester
        DerivationTester(**kwargs).load_data()
        # Prime the compounds indexer
        CompoundIndexer(**kwargs).load_data()

        # Initialize the Classifier object
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.mode = kwargs.get('mode', None)
        self.iteration = kwargs.get('iteration', 0)

        # Managers for plugging Bayes classification results into senses
        self.bayes = {mode: BayesCompounds(**kwargs) for mode in
            ('bias_low', 'bias_high')}
        self.bayes['main'] = BayesClassifier(**kwargs)

    def prepare_output_directories(self):
        if self.mode != 'test':
            for dirname in triage:
                dir = os.path.join(self.output_dir, dirname)
                if os.path.isdir(dir):
                    shutil.rmtree(dir)
                os.mkdir(dir)

    def classify(self):
        running_totals = {t: 0 for t in triage}
        for letter in letters:
            print('\tClassifying %s (Iteration #%d)...' % (letter, self.iteration))

            # Load Bayes evaluations for all the senses in this letter
            print('\t\tLoading Bayes data for %s...' % letter)
            for name, manager in self.bayes.items():
                if name == 'main':
                    manager.load_results(letter)
                else:
                    manager.load_results(letter, name)
            print('\t\tContinuing...')

            if self.mode == 'test':
                self.compound_tracer = open(os.path.join(self.resources_dir,
                    'compounds', 'trace', letter + '.txt'), 'w')

            self.buffer = {t: [] for t in triage}
            self.main_sense_of_entry = None
            self.previous_entry_id = 0
            loader = PickleLoader(self.input_dir, letters=letter)

            for sense in loader.iterate():
                # Determine whether this sense is considered tractable
                if sense.is_intractable():
                    intractable = True
                else:
                    intractable = False

                # Plug in any results for this sense previously
                #  obtained by the Bayes classifiers
                sense.bayes = BayesManager()
                for name, manager in self.bayes.items():
                    result = manager.seek_sense(sense.entry_id, sense.node_id)
                    sense.bayes.insert(name, result)

                # Main classification process
                #  (We only bother if it's a tractable sense)
                if not intractable:
                    selected_class, runners_up = self._core_classifier(sense)
                else:
                    selected_class, runners_up = (None, [])

                # Store the top Bayes classification for this sense
                try:
                    bayes_classification = sense.bayes.ids()[0]
                except IndexError:
                    bayes_classification = None
                bayes_confidence = sense.bayes.confidence()

                # Strip out any temporary attributes added to the sense
                #  as part of the classifier's work.
                #  (This saves space when re-pickling the sense)
                sense.strip_attributes()
                # ...then add back Bayes classification + confidence
                sense.bayes_classification = bayes_classification
                sense.bayes_confidence = bayes_confidence

                # Store result in the relevant buffer, and increment
                #  running totals
                if intractable:
                    self.buffer['intractable'].append(sense)
                    running_totals['intractable'] += 1
                elif selected_class is None:
                    self.buffer['unclassified'].append(sense)
                    running_totals['unclassified'] += 1
                else:
                    sense.class_id = selected_class.id
                    sense.reason_text = selected_class.reason_text
                    sense.reason_code = selected_class.reason_code
                    sense.runners_up = runners_up
                    self.buffer['classified'].append(sense)
                    running_totals['classified'] += 1

                # Update previous_entry with the current sense's
                #  entry ID - so that on the next iteration we can check
                #  if the parent entry has changed.
                self.previous_entry_id = sense.entry_id

            print('\t\t%s' % self._running_score(running_totals))
            if self.mode != 'test':
               self.flush_buffer(letter)

            if self.mode == 'test':
                self.compound_tracer.close()


    def flush_buffer(self, letter):
        """Pickle sense objects in the three triage categories to output
        files
        """
        for t in triage:
            outfile = os.path.join(self.output_dir, t, letter)
            with open(outfile, 'wb') as fh:
                for sense in self.buffer [t]:
                    pickle.dump(sense, fh)
        self.buffer = {t: [] for t in triage}

    def _running_score(self, stats):
        total = stats['classified'] + stats['unclassified']
        if total:
            pc = stats['classified'] / total
        else:
            pc = 0
        return 'resolved {m}/{t} ({percent:.2%})  intractable={i}'.format(
            m=stats['classified'], t=total, i=stats['intractable'], percent=pc)

    def _core_classifier(self, sense):
        """
        Core process for computing the classification for a given
        sense.
        """
        # Recalculate the main sense for this entry (if the entry
        #  has changed since the last sense processed)
        if self.previous_entry_id != sense.entry_id:
            self._update_main_sense(sense)

        # Attributive noun uses get treated like adjectives
        if (sense.wordclass == 'NN' and
                sense.definition is not None and
                re.search(r'^(also |used |also used |)(attrib\.|attributive)',
                sense.definition.lower(), re.I)):
            sense.wordclass = 'JJ'
            self.attributive_noun_sense = True
        else:
            self.attributive_noun_sense = False

        # If it's a compound (defined or undefined), we get results for
        #  formal compound analysis (i.e. based mainly on the form of
        #  the lemma, ignoring the definition (if any) at this stage).
        if (sense.subentry_type != 'derivative' and
                sense.first_element() is not None and
                sense.last_element() is not None):
            sense.compound_analysis = formal_compound_analysis.analyse(
                sense, self.main_sense_of_entry)
            # Log the compound analysis in the compound_tracer file (if
            #  this is a test run)
            if self.mode == 'test' and sense.compound_analysis:
                self._trace_compound_analysis(sense)
        else:
            sense.compound_analysis = formal_compound_analysis.null_result()

        # Get classifications based on Bayes evaluations and/or subject
        #  labelling
        (sense.topical_classification, sense.bayes_based_classifications,
            sense.label_based_classifications) = topical_classification(sense)

        #=============================================
        # Main classification routines - we run each approach in turn,
        #   and append the results to the candidate_classifications list.
        #   (Null results get weeded out at the end.)
        #=============================================

        candidate_classifications = []
        if sense.equals_crossreference() is not None:
            candidate_classifications.append(equals_cross_reference(sense))

        if (self.iteration == 2 or
                self.mode == 'test' or
                sense.equals_crossreference() is None):
            if sense.wordclass == 'NN':
                candidate_classifications.append(compare_binomials(sense))

            if sense.subentry_type == 'derivative':
                candidate_classifications.append(infer_derivative(sense,
                    self.main_sense_of_entry))

            if sense.cf_crossreference() is not None:
                candidate_classifications.append(cf_cross_reference(sense))

            candidate_classifications.append(lemma_as_superordinate(sense))

            if sense.is_only_sense():
                candidate_classifications.append(infer_from_neighbouring_wordclass(sense))

            if (sense.is_subentry and
                    sense.is_first() and
                    sense.senses_in_entry <= 3 and
                    sense.etyma):
                candidate_classifications.append(infer_from_etyma(sense))

            if sense.synonyms:
                candidate_classifications.append(triangulate_synonyms(sense))

            if sense.synonyms:
                candidate_classifications.append(match_single_synonym(sense))

            if sense.is_affix_subentry():
                candidate_classifications.append(affix_subentry(sense))

            candidate_classifications.append(infer_from_superordinate(sense))

            if not sense.is_subentry and sense.etyma and sense.subjects:
                candidate_classifications.append(infer_from_etyma(sense, subjectFilter=True))

            if sense.wordclass == 'NN':
                candidate_classifications.append(superordinate_adjective_state(sense))

            if sense.wordclass in ('NN', 'JJ', 'VB'):
                candidate_classifications.append(superordinate_lookup(sense))

            if sense.synonyms:
                candidate_classifications.append(synonym_main_sense(sense))

            if sense.wordclass in ('NN', 'JJ', 'VB'):
                candidate_classifications.append(superordinate_lookup(sense, panic=True))

            if self.attributive_noun_sense:
                candidate_classifications.append(attributive_of_noun(sense,
                    self.main_sense_of_entry))

            if sense.compound_analysis:
                candidate_classifications.append(formal_analysis(sense))

        # Clean up (remove null/duplicate classification)
        candidate_classifications = classifications_cleanup(
            candidate_classifications)

        # Promote classifications that match the Bayes evaluation
        candidate_classifications = apply_bayes_filter(sense,
            candidate_classifications, mode='promote')

        # Final attempts: resort to Bayes-based classification
        if self.iteration == 2 or self.mode == 'test':
            bayesclass = classify_by_bayes(sense)
            if bayesclass:
                candidate_classifications.append(bayesclass)

        #=============================================
        # Clean-up of any results emerging from the main
        #  classification routines
        #=============================================

        if candidate_classifications:
            # If the candidate classifications are not yet specific enough,
            #  see if there's any way to refine them
            # - first using binomials identified in quotations
            if sense.wordclass == 'NN' and sense.quotations_binomials:
                candidate_classifications = refine_by_binomial(
                    candidate_classifications,
                    sense.quotations_binomials
                )
            #  - then by examining how neighbouring senses are classified
            neighbours = [n for n in self.current_entry_profile if
                          n.parent is not None and
                          n.parent.wordclass is None and
                          n.probability > 0.3]
            if neighbours:
                candidate_classifications = [refine_by_neighbours(sense, t,
                                             neighbours) for t in
                                             candidate_classifications]
            # - then by subject labels
            if sense.subject_classes():
                candidate_classifications = [refine_by_subject_labels(
                                             sense, t) for t in
                                             candidate_classifications]

        # Clean up (again)
        candidate_classifications = classifications_cleanup(
            candidate_classifications)

        # Restrict candidate classifications to just those that fit
        #  within the constraints derived from Bayesian evaluation
        candidate_classifications = apply_bayes_filter(sense,
            candidate_classifications, mode='filter')

        # Return the best candidate, and return the others as runners-up
        if candidate_classifications:
            runners_up_ids = find_runners_up(sense, candidate_classifications)
            return candidate_classifications[0], runners_up_ids
        else:
            return None, []

    def _trace_compound_analysis(self, sense):
        self.compound_tracer.write(('=' * 100) + '\n')
        self.compound_tracer.write(sense.compound_analysis.trace())
        self.compound_tracer.write('\n\n\n')

    def _update_main_sense(self, current_sense):
        """Updates self.main_sense_of_entry to the main sense for the entry
        containing the current sense.
        """
        self.main_sense_of_entry = main_sense_finder.main_sense(
            lemma=current_sense.entry_lemma,
            refentry=current_sense.entry_id)
        self.current_entry_profile = ranked_sense_summary(
            refentry=current_sense.entry_id, level=5, omit_null=True)


def find_runners_up(sense, candidate_classifications):
    """
    Find up to two runner-up classes which will be stored in addition
    to the primary selected class.
    """
    if not candidate_classifications:
        return [None, None,]

    winning_class = candidate_classifications[0]

    # First,. use all the runners-up from candidate_classifications
    if len(candidate_classifications) > 1:
        runners_up_classes = candidate_classifications[1:]
    else:
        runners_up_classes = []

    # Extend with other possibilities derived from compound analysis
    #  and Bayes analysis
    if sense.compound_analysis.best_guess() is not None:
        runners_up_classes.extend([g.target for g in
            sense.compound_analysis.best_guesses])
    if sense.topical_classification is not None:
        runners_up_classes.append(sense.topical_classification)
    if sense.bayes.confidence() >= 5:
        runners_up_classes.extend(sense.bayes_based_classifications)
    runners_up_classes.extend(sense.label_based_classifications)

    # Filter out runners-up that are too closely related to the winning
    #  class, or too closely related to classes already picked
    #  as runners up.
    runners_up_filtered = []
    seen = [winning_class,]
    for runner_up in runners_up_classes:
        omit = False
        if any([s.id == runner_up.id or s.is_same_branch(runner_up) for s in seen]):
            omit = True
        else:
            for s in seen:
                common_ancestor = s.common_ancestor(runner_up)
                if common_ancestor is not None and common_ancestor.level >= 4:
                    omit = True
                    break
        if not omit:
            seen.append(runner_up)
            runners_up_filtered.append(runner_up)
            if len(runners_up_filtered) == 2:
                break

    # Convert to IDs
    runners_up_ids = [r.id for r in runners_up_filtered]
    # Pad with null values (in case we don't yet have two runners up)
    runners_up_ids.extend([None, None])
    # Return the top two IDS
    return runners_up_ids[0:2]


def equals_cross_reference(sense):
    xr = sense.equals_crossreference()
    target_senses, sense_count = tdb.cross_reference_target(lemma=xr.lemma,
        refentry=xr.refentry, refid=xr.refid, wordclass=sense.wordclass)

    if target_senses:
        hiscores = [t for t in target_senses
            if t.rating() == target_senses[0].rating()]
        hiscores.sort(key=lambda i: i.node_size(), reverse=True)
        if hiscores[0].thesclass is not None:
            match = hiscores[0].thesclass
            match.reason_text = 'Equivalent to %s' % hiscores[0].lemma
            match.reason_code = 'eqxr'
            return match
    return None


def cf_cross_reference(sense):
    """
    If the current sense has 'cf'-type cross-reference, the classification
    of the target sense is taken as a good guide to the classification
    of the current sense.

    If the target sense and the current sense are in the same wordclass and
    have the same end word-ending, we assume that the current sense should
    go in the target sense's class (similar to how 'equals'-type xrefs are
    treated.

    Otherwise, we put the current sense at the top of the equivalent
    wordclass-level branch.
    """
    xr = sense.cf_crossreference()
    # Nb don't specify a wordclass here, since the target wordclass may well
    #  be different from the current sense's wordclass
    target_senses, sense_count = tdb.cross_reference_target(lemma=xr.lemma,
        refentry=xr.refentry, refid=xr.refid)

    # Don't attempt if the target is too ambiguous (too many possible senses)
    if target_senses and sense_count <= 3:
        high_scores = [t for t in target_senses
            if t.rating() == target_senses[0].rating()]
        high_scores.sort(key=lambda i: i.node_size(), reverse=True)
        if high_scores[0].thesclass is not None:
            target = high_scores[0]
            if (target.wordclass == sense.wordclass and
                target.lemma[-2:] == sense.lemma[-2:]):
                match = target.thesclass
            elif target.wordclass == sense.wordclass:
                match = target.wordclass_parent()
            else:
                match = tdb.equivalent_class(target.thesclass, sense.wordclass)
            if match is not None:
                match.reason_text = 'Analogy with target of cf-type xref ("%s")' % target.lemma
                match.reason_code = 'cfxr'
            return match

    return None


def formal_analysis(sense):
    if sense.compound_analysis.forced_result is not None:
        match = sense.compound_analysis.forced_result
    elif sense.compound_analysis.best_guess() is not None:
        match = sense.compound_analysis.best_guess_class()
    else:
        match = None
    if match is not None:
        match.reason_text = 'Inferred from compound lemma form'
        match.reason_code = 'comp'
        return match
    else:
        return None


def lemma_as_superordinate(sense):
    """
    Check if the lemma is used anywhere as a superordinate
    """
    match = None
    riskable = False

    if sense.wordclass == 'NN' and len(sense.lemma) > 8:
        # If this is a subentry, then we can risk it without checking
        #   the database
        if (sense.is_subentry and
        sense.lemma.lower() != sense.entry_lemma.lower() and
        len(sense.lemma) > 8):
            riskable = True

        # ...But if it's a main sense, we check that (a) it's the only sense
        #  in its entry (or entry block), and then confirm that it's the only
        #  sense recorded in the database
        elif sense.senses_in_entry == 1:
            instances = tdb.search(lemma=sense.lemma)
            if len(instances) == 1 and instances[0].refid == sense.node_id:
                riskable = True

    if riskable:
        qterm = sense.lemma.lower().replace('-', '').replace(' ', '')
        record = tdb.get_superordinate_record(qterm)
        if record is not None:
            if sense.bayes.branches():
                # Look for commonalities with Bayes branches
                bayes_ancestors = sense.bayes.ancestors(level=2)
                record_ancestors = set([b.thesclass.ancestor(level=2)
                    for b in record.branches])
                common_branches = set.intersection(bayes_ancestors,
                    record_ancestors)
                for b in record.branches:
                    if b.thesclass.ancestor(level=2) in common_branches:
                        match = b.thesclass
                        break
            else:
                match = record.branches[0].thesclass

    if match is not None:
        match.reason_text = 'Lemma appears elsewhere as a superordinate'
        match.reason_code = 'lass'
        return match
    else:
        return None


def infer_derivative(sense, main_sense_of_entry):
    equiv = None
    if (main_sense_of_entry is not None and
        not main_sense_of_entry.is_affix() and
        main_sense_of_entry.thesclass is not None):
        # Take precedent from the main sense of the parent entry
        equiv = tdb.equivalent_class(main_sense_of_entry.thesclass, sense.wordclass)
        if equiv is not None:
            equiv.reason_text = 'Parallel to "%s"' % main_sense_of_entry.lemma
            equiv.reason_code = 'driv'
    if equiv is None:
        # Take precedent from other sibling derivatives
        candidates = tdb.ranked_search(refentry=sense.entry_id,
            thes_linked=True, currentOnly=True)
        candidates = [c for c in candidates if c.is_derivative() and
                      not ' ' in c.lemma and
                      c.superclass() is not None]
        if candidates:
            j = defaultdict(int)
            for c in candidates:
                j[c.superclass()] += 1
            parents = [p for p, num in j.items() if num == max(j.values())]
            # If there's more than one possible parent, pick the one with
            #  the largest branch
            parents.sort(key=lambda p: p.branch_size, reverse=True)
            equiv = tdb.child_wordclass_branch(parents[0], sense.wordclass)
            if equiv is None:
                equiv = parents[0]
            if equiv is not None:
                equiv.reason_text = 'Parallel to %s' % ', '.join(
                    ['"%s"' % (c.lemma,) for c in candidates if c.lemma])
                equiv.reason_code = 'driv'
    return equiv


def attributive_of_noun(sense, main_sense_of_entry):
    """
    An attrib. sense of a noun is treated as the adj. equivalent
    of the main sense of the entry (or of a particular sense, if referenced)
    """
    # Use a particular sense if it's cross-referenced
    #  Check that it's an internal cross-reference to a main sense
    #   (hence no lemma)
    xrefs = [xr for xr in sense.cross_references if
        xr.refentry == sense.entry_id and xr.lemma is None]
    if xrefs:
        target_sense = tdb.highest_ranked(lemma=sense.lemma,
                                          wordclass='NN',
                                          refentry=xrefs[0].refentry,
                                          refid=xrefs[0].refid)
        if target_sense is not None and target_sense.thesclass is not None:
            equiv = tdb.equivalent_class(target_sense.thesclass, 'JJ')
            equiv.reason_text = 'Adjective equivalent of cross-referenced noun sense'
            equiv.reason_code = 'attb'
            return equiv
        elif target_sense is not None:
            return None

    # ... otherwise, default to the main sense of the entry
    if (main_sense_of_entry is not None and
        main_sense_of_entry.thesclass is not None):
        equiv = tdb.equivalent_class(main_sense_of_entry.thesclass, 'JJ')
        equiv.reason_text = 'Adjective equivalent of main noun sense'
        equiv.reason_code = 'attb'
        return equiv
    else:
        return None


def affix_subentry(sense):
    stem = sense.entry_lemma.strip('-')
    if sense.lemma.startswith(stem) and re.search(r'^[a-zA-Z]+$', stem):
        ending = re.sub(r'^' + stem, '', sense.lemma)
        ending = ending.strip(' -')
        if len(ending) < 4:
            target_sense = None
        elif sense.subjects:
            target_sense = tdb.highest_ranked(lemma=ending,
                                              wordclass=sense.wordclass,
                                              subjects=sense.subjects)
        else:
            target_sense = main_sense_finder.main_sense(lemma=ending,
                                                        wordclass=sense.wordclass)
        if target_sense is not None and target_sense.thesclass is not None:
            match = target_sense.thesclass
            match.reason_text = 'Inferred from last element ("%s")' % ending
            match.reason_code = 'driv'
            return match
    return None


def compare_binomials(sense):
    if sense.wordclass != 'NN':
        return None
    match = None
    for b in sense.binomials:
        class_id = binomial_checker.find_class(b)
        if class_id is not None:
            match = tdb.get_thesclass(class_id)
    if match is None:
        for g in sense.genera:
            class_id = binomial_checker.find_class(g)
            if class_id is not None:
                match = tdb.get_thesclass(class_id)
    if match is not None:
        match.reason_text = 'Taxonomic name: %s' % ', '.join(
            sense.binomials.union(sense.genera))
        match.reason_code = 'txny'
        return match
    else:
        return None


def triangulate_synonyms(sense):
    match = synonymchecker.triangulate_synonyms(sense)
    if match is not None:
        match.reason_text = 'Analogy with synonym: %s' % ', '.join(
            ['"%s"' % (s,) for s in sense.synonyms])
        match.reason_code = 'syns'
        return match
    else:
        return None


def match_single_synonym(sense):
    match, synonym_used = synonymchecker.match_single_synonym(sense)
    if match is not None:
        match.reason_text = 'Analogy with synonym: %s' % synonym_used
        match.reason_code = 'syns'
        return match
    else:
        return None


def synonym_main_sense(sense):
    match, synonym_used = synonymchecker.synonym_main_sense(sense)
    if match is not None:
        match.reason_text = 'Analogy with synonym: %s' % synonym_used
        match.reason_code = 'syns'
        return match
    else:
        return None


def infer_from_etyma(sense, subjectFilter=False):
    etymon, target_instance = (None, None)
    if len(sense.etyma) == 1 and sense.etyma[0][0] == sense.lemma:
        etymon = sense.etyma[0]
    elif (len(sense.etyma) == 2 and
        re.search(r'^[a-zA-Z]+$', sense.etyma[0][0]) and
        re.search(r'^-[a-z]+$', sense.etyma[1][0])):
        suffix = sense.etyma[1][0]
        if (deriv_tester.is_neutral_suffix(suffix) or
            (suffix in ('-ist', '-ian', '-ful') and sense.wordclass == 'JJ')):
            etymon = sense.etyma[0]

    if etymon is not None:
        # First try to find the exact sense, in case the etymon points to a
        #  specific sense - see e.g. lam n./3
        target_instance = tdb.highest_ranked(lemma=etymon[0],
                                             refentry=etymon[1],
                                             refid=etymon[2],
                                             exact_sense=True)
        # ...but if the etymon just points to an entry in general, find that
        #  entry's main sense
        if target_instance is None and not subjectFilter:
            target_instance = main_sense_finder.main_sense(lemma=etymon[0],
                                                           refentry=etymon[1])
        elif target_instance is None and subjectFilter:
            main_sense = tdb.highest_ranked(lemma=etymon[0],
                                            refentry=etymon[1],
                                            subjects=sense.subjects)
            if main_sense is not None and main_sense.entry_size < 100:
                target_instance = main_sense

        if target_instance is not None:
            # Check if the target is also referenced in the sense's
            #  cross-references (in case a particular sense is pointed to,
            #  as in 'nocturning').
            for xr in sense.cross_references:
                if (xr.lemma == target_instance.lemma and
                    xr.refentry == target_instance.refentry):
                    specific_target = tdb.highest_ranked(lemma=xr.lemma,
                                                         refentry=xr.refentry,
                                                         refid=xr.refid,
                                                         exact_sense=True)
                    if specific_target is not None:
                        target_instance = specific_target
                    break

    if target_instance is not None and target_instance.thesclass is not None:
        if target_instance.wordclass == sense.wordclass:
            match = target_instance.thesclass.wordclass_parent()
        else:
            match = tdb.equivalent_class(target_instance.thesclass, sense.wordclass)
        if match is not None:
            match.reason_code = 'etym'
            match.reason_text = 'Analogy with "%s" in etymology' % etymon[0]
        return match
    else:
        return None


def infer_from_neighbouring_wordclass(sense):
    match = None
    if sense.wordclass in ('JJ', 'VB'):
        opposite_class = 'NN'
    elif sense.wordclass in ('NN', 'RB'):
        opposite_class = 'JJ'
    else:
        opposite_class = None
    if opposite_class is not None:
        opposite = tdb.highest_ranked(lemma=sense.lemma,
                                      refentry=sense.entry_id,
                                      wordclass=opposite_class)
        if opposite is not None and opposite.thesclass is not None:
            match = tdb.equivalent_class(opposite.thesclass, sense.wordclass)

    if match is not None:
        match.reason_code = 'nbor'
        match.reason_text = 'Inferred from neighbouring %s branch' % opposite_class
    return match


def infer_from_superordinate(sense):
    match = superordinate_manager.find_branch_from_superordinate(sense)
    if match is not None:
        if sense.wordclass == 'JJ':
            match.reason_code = 'adeq'
            match.reason_text = 'Adjective equivalent of "%s"' % sense.superordinate
        else:
            match.reason_code = 'supe'
            match.reason_text = 'Classification of superordinate "%s" ("%s")'\
                % (sense.superordinate, sense.superordinate_full)
    return match


def superordinate_lookup(sense, **kwargs):
    match = superordinate_manager.superordinate_lookup(sense, **kwargs)
    if match is not None and match.wordclass is not None:
        if sense.wordclass == 'JJ':
            match = tdb.equivalent_class(match, 'JJ')
            match.reason_code = 'adeq'
            match.reason_text = 'Adjective equivalent of "%s"' % sense.superordinate
        else:
            match.reason_code = 'supe'
            match.reason_text = 'Classification of superordinate "%s" ("%s")'\
                % (sense.superordinate, sense.superordinate_full)
        #if sense.wordclass == 'VB':
        #    print('\n----------------------------------------')
        #    print(trace_sense(sense))
        #    print(trace_class(match))
        return match
    else:
        return None


def superordinate_adjective_state(sense):
    match = superordinate_manager.superordinate_adjective_state(sense)
    if match is not None and match.wordclass is not None:
        match.reason_code = 'supe'
        match.reason_text = 'Classification of superordinate "%s" ("%s")'\
            % (sense.superordinate, sense.superordinate_full)
        return match
    else:
        return None


def classify_by_bayes(sense):
    if sense.topical_classification is not None:
        match = sense.topical_classification
        match.reason_code = 'topc'
        match.reason_text = 'Estimated topic (based on Bayes classifier)'
        return match
    else:
        return None


#================================================================
# Functions to try to refine candidate classes, i.e. switch a higher-level
#  classification to a more granular classification
#================================================================

def refine_by_binomial(candidate_classifications, qbinomials):
    """
    Refine classification using binomials found in quotations.
    """
    def test_descent(current_class, possible_refinements):
        new_class = None
        for binomial_class in possible_refinements:
            if (binomial_class != current_class and
                    binomial_class.is_descendant_of(current_class)):
                new_class = binomial_class
                break
        if new_class is not None:
            new_class.reason_code = current_class.reason_code
            new_class.reason_text = current_class.reason_text
            return new_class
        else:
            return current_class

    binomial_ids = set([binomial_checker.find_class(b) for b in qbinomials])
    binomials = [tdb.get_thesclass(class_id) for class_id in binomial_ids
                 if class_id is not None]
    if binomials:
        candidate_classifications = [test_descent(t, binomials) for t in
                                     candidate_classifications]
    return candidate_classifications






def refine_by_neighbours(sense, current_class, neighbours):
    """
    Refine classification using the classification of other senses
    in the same entry.
    """
    new_class = None
    for n in neighbours:
        if n.parent.is_descendant_of(current_class):
            new_class = n.parent
            break
    if new_class is not None:
        new_class.reason_code = current_class.reason_code
        new_class.reason_text = current_class.reason_text
        return new_class
    else:
        return current_class


def refine_by_subject_labels(sense, current_class):
    """
    Refine classification based on explicit subject labels.
    """
    if current_class.wordclass is not None:
        return current_class
    if any([b == current_class for b in sense.subject_classes()]):
        return current_class

    new_class = None
    possible_refinements = [b for b in sense.subject_classes()
                            if b != current_class and
                               b.is_descendant_of(current_class)]
    if len(possible_refinements) == 1:
        new_class = possible_refinements[0]
    elif len(possible_refinements) > 1:
        for level in (6, 5, 4, 3):
            ancestors = set([b.ancestor(level=level) for b in possible_refinements])
            ancestors = list(ancestors)
            if (len(ancestors) == 1 and
                    ancestors[0] is not None and
                    ancestors[0] != current_class and
                    ancestors[0].is_descendant_of(current_class)):
                new_class = ancestors[0]
                break

    if new_class is not None:
        new_class.reason_code = current_class.reason_code
        new_class.reason_text = current_class.reason_text
        return new_class
    else:
        return current_class


def classifications_cleanup(candidate_classifications):
    """
    Clean up the set of candidate classifications.
    Removes null and duplicate classifications
    """
    # Remove any null/dummy candidate classifications
    candidate_classifications = [t for t in candidate_classifications
                                 if t is not None]

    # Remove duplicates
    seen = set()
    tmp = []
    for c in candidate_classifications:
        if c.id not in seen:
            tmp.append(c)
            seen.add(c.id)
    candidate_classifications = tmp

    # Make sure that every candidate classification has reason text/code
    for t in candidate_classifications:
        try:
            t.reason_text
        except AttributeError:
            t.reason_text = None
        try:
            t.reason_code
        except AttributeError:
            t.reason_code = None

    return candidate_classifications
