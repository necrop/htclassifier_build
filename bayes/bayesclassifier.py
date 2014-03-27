
import os
import string
import pickle
from collections import defaultdict

from lex.entryiterator import EntryIterator
from .senseparser.senseparser import SenseParser
from .bayesresult import BayesResult, BayesSense
from .pickleloader import PickleLoader
from .classifiers_io import (write_classifiers, write_priors_file,
                             load_classifiers, options_list,)

# Classifiers will only be built for thesaurus branches between these sizes
branch_size_min = 2500
branch_size_max = 100000

# Only keywords equal to or above this frequency will be used in the
#  classifiers
keyword_threshold = 20
citation_threshold = 30


class BayesClassifier(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.parent_dir = os.path.join(self.resources_dir, 'bayes')
        self.subject_map_file = os.path.join(self.resources_dir, 'subject_ontology.xml')
        self.senses_dir = os.path.join(self.parent_dir, 'senses')
        self.classifiers_dir = os.path.join(self.parent_dir, 'classifiers')
        self.rank_dir = os.path.join(self.parent_dir, 'rankfiles')
        self.output_dir = os.path.join(self.parent_dir, 'results')
        self.priors_file = os.path.join(self.parent_dir, 'priors.txt', )
        self.classifiers = {}

    def store_features_by_sense(self):
        """
        Iterate through each sense (both training and new data), parsing
        and storing the set of features that will be used by the Bayes
        classifier. This store is later used both to build the classifiers
        (picking out the training senses only) and as a cache of data
        for classifying the new senses.

        Features include:
        - definition keywords
        - quotation keywords
        - author names or titles from quotations
        - keywords from titles
        - subject labels
        - usage labels
        - first date
        - wordclass

        Lemma words (components derived by decomposing the lemma) are also
        collected here. Lemma words are not used directly for the
        Bayes classifier itself (they're folded into the set of definition
        keywords), but are used separately to help classify compounds.
        It's just more efficient to parse them along with everything else
        as part of this process.
        """
        sense_parser = SenseParser(self.parent_dir, self.subject_map_file)
        for letter in string.ascii_uppercase:
            file_filter = 'oed_%s.xml' % letter
            ei = EntryIterator(dictType='oed',
                               fixLigatures=True,
                               verbosity='low',
                               fileFilter=file_filter)

            outfile = os.path.join(self.senses_dir, letter)
            with open(outfile, 'wb') as filehandle:
                for entry in ei.iterate():
                    entry.share_quotations()
                    etyma = entry.etymology().etyma()
                    for sense in entry.senses():
                        sense_data_object = sense_parser.parse_sense(
                            sense,
                            etyma,
                            entry.id)
                        pickle.dump(sense_data_object, filehandle)

    def build_rank_files(self):
        """
        Build ordered lists of the most frequent tokens for each
        feature type.

        Note that we don't build a rank file for quotation keywords.
        When filtering quotation keywords, we'll use the rank file for
        *definition* keywords. This avoids muddying the classifiers with
        extraneous words from quotation text.
        """
        feature_types = ('definition', 'citation', 'title_word', 'lemma_word',
                         'subject', 'usage', 'date', 'wordclass')

        rankings = {f: defaultdict(int) for f in feature_types}
        pl = PickleLoader(self.senses_dir)
        for s in [s for s in pl.iterate() if s.branches]:
            if len(rankings['definition']) < 500000:
                for token in s.definition_keywords:
                    rankings['definition'][token] += 1
            if len(rankings['citation']) < 100000:
                for citation in s.citations:
                    rankings['citation'][citation] += 1
            if len(rankings['title_word']) < 100000:
                for word in s.title_words:
                    rankings['title_word'][word] += 1
            for word in s.lemma_words:
                rankings['lemma_word'][word] += 1
            for subject in s.subjects:
                rankings['subject'][subject] += 1
            for usage in s.usage_labels:
                rankings['usage'][usage] += 1
            for d in s.date:
                rankings['date'][d] += 1
            for d in s.wordclass:
                rankings['wordclass'][d] += 1

        for f in feature_types:
            filepath = os.path.join(self.rank_dir, f + '.txt')
            tokenlist = [(t, v) for t, v in rankings[f].items() if v > 3]
            tokenlist.sort(key=lambda t: t[1], reverse=True)
            with open(filepath, 'w') as filehandle:
                for c in tokenlist:
                    j = '%s\t%d\n' % (c[0], c[1])
                    filehandle.write(j)

    def _top_features(self, **kwargs):
        """
        Load the top x features from the a given rank file.

        x can be specified either by 'num' (number of rows returned)
        or by 'min_frequency' (minimum frequency of rows returned).

        Defaults to num=1000
        """
        file = kwargs.get('file')
        num = kwargs.get('num')
        min_frequency = kwargs.get('min_frequency')
        if num is None and min_frequency is None:
            num = 1000
        features = []
        with open(file, 'r') as fh:
            for row in fh:
                feature, frequency = row.strip().split('\t')
                frequency = int(frequency)
                if ((num is not None and len(features) == num) or
                    (min_frequency is not None and frequency < min_frequency)):
                    break
                features.append((feature, frequency))
        return features

    def make_classifiers(self):
        # Set up data structures
        thesaurus_ids = options_list()

        # Dictionary of all the features we'll be using. The value is a
        #   defaultdict where we'll keep a running total of counts
        #   for each individual thesaurus class
        # Every feature gets a capital-letter prefix (e.g. 'S_' for subjects)
        #  to distinguish this from the same string representing another
        #  feature
        features = {}
        for feature_type, prefix, min_frequency in (
            ('definition', 'D_', keyword_threshold),
            ('definition', 'Q_', keyword_threshold),
            ('citation', 'C_', citation_threshold),
            ('title_word', 'T_', citation_threshold),
            ('subject', 'S_', 0),
            ('usage', 'U_', 0),
            ('date', 'Y_', 0),
            ('wordclass', 'W_', 0),
        ):
            file = os.path.join(self.rank_dir, feature_type + '.txt')
            for feature, frequency in self._top_features(file=file,
                min_frequency=min_frequency):
                features[prefix + feature] = defaultdict(int)
        # Add in binomial
        features['E_binomial'] = defaultdict(int)

        # Number of senses for each thesaurus ID (used later to calculate
        #  prior probabilities)
        number_of_senses = {id: 0 for id in thesaurus_ids}

        # Run through all the stored senses, building counts for each keyword
        total_senses = 0
        pl = PickleLoader(self.senses_dir)
        for sense in [s for s in pl.iterate() if s.branches]:
            total_senses += 1

            # Get the relevant thesaurus IDs for this sense
            ids = [id for id in sense.branches if id in thesaurus_ids]

            # Increment the sense count for each of these IDs
            for id in ids:
                number_of_senses[id] += 1

            # Apply all the features to this set of IDs
            for dataset, prefix in (
                (sense.definition_keywords, 'D_'),
                (sense.quotation_keywords, 'Q_'),
                (sense.citations, 'C_'),
                (sense.title_words, 'T_'),
                (sense.subjects, 'S_'),
                (sense.usage_labels, 'U_'),
                (sense.date, 'Y_'),
                (sense.wordclass, 'W_'),
            ):
                for feature in [prefix + word for word in dataset]:
                    if feature in features:
                        for id in ids:
                            features[feature][id] += 1
            if sense.has_binomials:
                for id in ids:
                    features['E_binomial'][id] += 1

        write_classifiers(self.classifiers_dir, thesaurus_ids, features,
            number_of_senses, total_senses)

    def list_priors(self):
        write_priors_file(self.classifiers_dir, self.priors_file)

    def classify_new_senses(self):
        self.prior_probabilities, self.classifiers =\
            load_classifiers(self.classifiers_dir)

        for letter in string.ascii_uppercase:
            print('Bayes-classifying in %s...' % letter)
            output = []
            output_readable = []

            pl = PickleLoader(self.senses_dir, letters=letter)
            for sense in [s for s in pl.iterate() if not s.branches]:
                # Compute the top 20 results
                raw_results = self._classifyengine(sense)[0:20]
                # Package this into result-set object
                result_set = BayesSense(sense=sense, results=raw_results,)
                output.append(result_set)

                output_readable.append('\n--------------------------------')
                output_readable.append('%s\t%d#eid%d' % (sense.lemma,
                    sense.refentry, sense.refid))
                for r in raw_results:
                    output_readable.append('\t%s\t%f' % (
                        r.breadcrumb(), r.posterior))
                output_readable.append(' '.join(['(%s, %f)' % (token, prob)
                    for token, prob in raw_results[0].details]))

            # Output file for pickled result-set objects
            file1 = os.path.join(self.output_dir, letter)
            with open(file1, 'wb') as filehandle:
                for o in output:
                    pickle.dump(o, filehandle)

            # Human-readable output file
            file2 = os.path.join(self.output_dir, letter + '_readable.txt')
            with open(file2, 'w') as filehandle:
                for line in output_readable:
                    filehandle.write(line + '\n')

    def load_results(self, letter):
        """
        For a given letter, load all the results into memory,
        as a dictionary indexed by (entryID, nodeID) tuples.
        """
        file = os.path.join(self.output_dir, letter)
        results = []
        with open(file, 'rb') as filehandle:
            while 1:
                try:
                    results.append(pickle.load(filehandle))
                except EOFError:
                    break
        self.results = {(r.refentry, r.refid): r for r in results}

    def seek_sense(self, refentry, refid):
        """
        Return the result object for a given sense (assuming that the
        sense is one of these loaded into memory by load_results() )

        Arguments are (entryID, nodeID)
        """
        try:
            self.results
        except AttributeError:
            return None
        else:
            try:
                return self.results[(refentry, refid)]
            except KeyError:
                return None

    def _classifyengine(self, sense):
        prior_probabilities = self.prior_probabilities
        all_features = self.classifiers

        # Get the subset of all features that pertain to this sense
        probabilities = []
        for dataset, prefix in (
            (sense.definition_keywords, 'D_'),
            (sense.quotation_keywords, 'Q_'),
            (sense.citations, 'C_'),
            (sense.title_words, 'T_'),
            (sense.subjects, 'S_'),
            (sense.usage_labels, 'U_'),
            (sense.date, 'Y_'),
            (sense.wordclass, 'W_'),
        ):
            for feature in [prefix + word for word in dataset]:
                if feature in all_features:
                    probabilities.append((feature, all_features[feature]))
        if sense.has_binomials:
            probabilities.append(('[binomials]', all_features['E_binomials']))

        # Calculate the posterior probabilities for each candidate
        #  thesaurus ID (i.e. thesaurus branch) in turn
        ranking = []
        for id, prior_probability in prior_probabilities.items():
            local_probabilities = [(f[0], f[1][id]) for f in
                                   probabilities if id in f[1]]

            # Sort features into alphabetical order - it's necessary that
            #  all results for a given sense have their features in the
            #  same order
            local_probabilities.sort(key=lambda f: f[0])

            # Since we're using log probabilities, rather than
            #  raw probabilities, we calculate the overall posterior
            #  probability by adding rather than multiplying the
            #  individual values.
            posterior_probability = prior_probability +\
                sum([f[1] for f in local_probabilities])

            bayes_result = BayesResult(
                id=id,
                prior=prior_probability,
                posterior=posterior_probability,
                details=local_probabilities,
            )
            ranking.append(bayes_result)

        # Sort so that the highest posterior probability is first
        ranking.sort(key=lambda r: r.posterior, reverse=True)
        return ranking
