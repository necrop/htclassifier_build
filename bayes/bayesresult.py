import math
import numpy

from .thesclasscache import ThesclassCache
thesclass_cache = ThesclassCache()


class BayesSense(object):

    """
    Set of results from the Bayes classifier (representing a single
    sense and the top 10 thesaurus classes it has been matched to).

    Basic attributes are:
        * lemma (sense lemma)
        * refentry (sense's entry ID)
        * refid (sense's node ID)
        * results (the list of top 10 results, in rank order)
        * details (list of features used, with the scores for the first result)
    """
    confidence_scale = [
        (1, 0), (3, 1), (5, 2), (7.5, 3), (10, 4), (15, 5),
        (20, 6), (30, 7), (40, 8), (50, 9), (1000000, 10)
    ]

    def __init__(self, **kwargs):
        sense = kwargs.get('sense')
        self.lemma = sense.lemma
        self.refentry = sense.refentry
        self.refid = sense.refid
        self.features = [f[0] for f in kwargs.get('results')[0].details]

        # To save space, we slim down the results so that each result
        #  consists only of the basic attributes 'id' and 'posterior'
        self.results = [make_compact_results(i, r) for i, r in
            enumerate(kwargs.get('results'))]

    def best_guess(self):
        if self.results:
            return self.results[0].thesclass()
        else:
            return None

    def num_features(self):
        return len(self.features)

    def details(self, index=0):
        try:
            self.results[index].details
        except AttributeError:
            return []
        else:
            return zip(self.features, self.results[index].details)

    def display_features(self):
        return ' | '.join(['%s = %0.3g' % (feature, score) for
            feature, score in self.details()])

    def recover_probabilities(self):
        """
        Recover relative probabilities (0 < p < 1) from the log scores
        stored with each result.
        """
        self._shift_scores()

        # Prior probabilities
        total = sum([math.exp(r.prior_shifted) for r in self.results])
        for r in self.results:
            if total:
                r.prior_probability = math.exp(r.prior_shifted) / total
            else:
                r.prior_probability = 0

        # Posterior probabilities
        total = sum([math.exp(r.posterior_shifted) for r in self.results])
        for r in self.results:
            if total:
                r.posterior_probability = math.exp(r.posterior_shifted) / total
            else:
                r.posterior_probability = 0

    def _shift_scores(self):
        """
        Shift probability scores so that all are positive, and the
        lowest is set to 0.

        Since we're dealing with log-probabilities here, shifting them
        all by the same amount preserves their relative probabilities.
        """
        # Prior probabilities
        bottom_score = min([r.prior for r in self.results])
        shift_distance = 0 - bottom_score
        for r in self.results:
            r.prior_shifted = r.prior + shift_distance

        # Posterior probabilities
        bottom_score = self.results[-1].posterior
        shift_distance = 0 - bottom_score
        for r in self.results:
            r.posterior_shifted = r.posterior + shift_distance

    def filtered_results(self, **kwargs):
        total_probability = kwargs.get('total_probability', 0.95)
        try:
            self._filters
        except AttributeError:
            self._filters = {}
        try:
            return self._filters[total_probability]
        except KeyError:
            running_total = 0
            filtered = []
            for r in self.results:
                filtered.append(r)
                running_total += r.posterior_probability
                if running_total >= total_probability:
                    break
            # Omit any result that has a delta < 1 (i.e. where the
            #  posterior probability is *lower* than the prior)
            #filtered = [r for r in filtered if r.delta() > 1]
            self._filters[total_probability] = filtered
            return self._filters[total_probability]

    def average_delta(self, **kwargs):
        if self.filtered_results(**kwargs):
            return numpy.mean([r.delta() for r in
                               self.filtered_results(**kwargs)])
        else:
            return 0

    def confidence(self):
        try:
            return self._confidence
        except AttributeError:
            self._confidence = None
            ad = self.average_delta()
            for score, grading in self.confidence_scale:
                if ad < score:
                    self._confidence = grading
                    break
            # Reduce score if very low feature count
            if self._confidence >= 5:
                if self.num_features() <= 5:
                    self._confidence -= 2
                elif self.num_features() <= 10:
                    self._confidence -= 1
            return self._confidence


class BayesResult(object):

    """
    Single result from the Bayes classifier (representing the score
    for a single sense matched to a single thesaurus class)

    Basic attributes (supplied as keyword arguments) are:
        * id (thesaurus class ID)
        * prior (prior_probability)
        * posterior (posterior_probability)
        * details
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def thesclass(self):
        return thesclass_cache.retrieve_thesclass(self.id)

    def breadcrumb(self):
        return self.thesclass().breadcrumb()

    def delta(self):
        """
        Calculate how far the probability has shifted from prior
        to posterior
        """
        if not self.prior_probability or not self.posterior_probability:
            return 0
        else:
            d = self.posterior_probability / self.prior_probability
        return d


def make_compact_results(i, r):
    """
    Return a slimmed-down copy of each result in the results set

    Retains score details for the top 5 results, discards them
    for all the others
    """
    if i >= 5:
        return BayesResult(id=r.id, prior=r.prior, posterior=r.posterior)
    else:
        details = [float('%0.3g' % f[1]) for f in r.details]
        return BayesResult(id=r.id, prior=r.prior, posterior=r.posterior,
                           details=details)

