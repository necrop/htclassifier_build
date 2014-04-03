import os
import string
import pickle
from collections import defaultdict

from bayes.pickleloader import PickleLoader
from bayes.bayesresult import BayesResult, BayesSense
from bayes.classifiers_io import (write_classifiers, load_classifiers,
                                  options_list)


class BayesCompounds(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.bayes_dir = os.path.join(self.resources_dir, 'bayes')
        self.senses_dir = os.path.join(self.bayes_dir, 'senses')
        self.rank_file = os.path.join(self.bayes_dir, 'rankfiles', 'lemma_word.txt')

        self.parent_dir = os.path.join(self.resources_dir, 'compounds', 'bayes')
        self.classifiers_dir = os.path.join(self.parent_dir, 'classifiers')
        self.output_dir = os.path.join(self.parent_dir, 'results')

    def _load_feature_list(self):
        features = {}
        with open(self.rank_file, 'r') as filehandle:
            for row in filehandle:
                feature, frequency = row.strip().split('\t')
                features[feature] = defaultdict(int)
        return features

    def make_classifiers(self):
        # Set up data structures
        thesaurus_ids = options_list()

        # Dictionary of all the features we'll be using
        features = self._load_feature_list()

        # Number of senses for each thesaurus class (used later to calculate
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
            for feature in sense.lemma_words:
                if feature in features:
                    for id in ids:
                        features[feature][id] += 1

        write_classifiers(self.classifiers_dir, thesaurus_ids, features,
                          number_of_senses, total_senses)

    def classify_new_senses(self, **kwargs):
        bias_first = kwargs.get('bias_first', 1)
        bias_last = kwargs.get('bias_last', 1)
        dirname = kwargs.get('dir', 'default')

        # Set up the directory that output will be sent to
        outdir = os.path.join(self.output_dir, dirname)
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

        # Load the classifiers into memory
        self.prior_probabilities, self.classifiers =\
            load_classifiers(self.classifiers_dir)

        # Adjust the values for '..._FIRST' or '..._LAST' features,
        #  so that these carry more or less weight than other features
        for feature, values in self.classifiers.items():
            for marker, weighting in (
                ('FIRST', bias_first),
                ('LAST', bias_last)
            ):
                if marker in feature and weighting != 1:
                    for id, old_log in values.items():
                        # Overwrite with the new log value
                        self.classifiers[feature][id] = old_log * weighting

        for letter in string.ascii_uppercase:
            print('Bayes-classifying in %s (%s)...' % (letter, dirname))
            output = []
            output_readable = []

            pl = PickleLoader(self.senses_dir, letters=letter)
            for sense in [s for s in pl.iterate() if not s.branches and
                          is_componentized(s)]:
                # Compute the top 20 results
                raw_results = self._classifyengine(sense)[0:20]
                # Package this into a result-set object
                result_set = BayesSense(sense=sense, results=raw_results,)
                output.append(result_set)

                output_readable.append('\n--------------------------------')
                output_readable.append('%s\t%d#eid%d' % (sense.lemma,
                    sense.refentry, sense.refid))
                for r in raw_results:
                    output_readable.append('\t%s\t%0.4g' % (
                        r.breadcrumb(), r.posterior))
                output_readable.append(result_set.display_features())

            # Output file for pickled result-set objects
            file1 = os.path.join(outdir, letter)
            with open(file1, 'wb') as filehandle:
                for o in output:
                    pickle.dump(o, filehandle)

            # Human-readable output file
            file2 = os.path.join(outdir, letter + '_readable.txt')
            with open(file2, 'w') as filehandle:
                for line in output_readable:
                    filehandle.write(line + '\n')

    def load_results(self, letter, subdir):
        """
        For a given letter, load all the results into memory,
        as a dictionary indexed by (entryID, nodeID) tuples.
        """
        file = os.path.join(self.output_dir, subdir, letter)
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
        sense is one of those loaded into memory by load_results() )

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
        for feature in sense.lemma_words:
            if feature in self.classifiers:
                probabilities.append((feature, self.classifiers[feature]))

        # Calculate the posterior probabilities for each candidate
        #  thesaurus ID (i.e. thesaurus branch) in turn
        ranking = []
        for id, prior_probability in prior_probabilities.items():
            local_probabilities = []
            for feature, values in [f for f in probabilities if id in f[1]]:
                value = values[id]
                #if 'FIRST' in feature:
                #    value -= 0.7
                local_probabilities.append((feature, value))
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


def is_componentized(sense):
    for w in sense.lemma_words:
        if 'FIRST' in w or 'LAST' in w:
            return True
    return False
