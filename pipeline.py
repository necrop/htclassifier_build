"""
Pipeline - Runs processes for building Classifier data
"""

import os

import classifierconfig as config


def dispatch():
    for function_name, status in config.PIPELINE:
        if status:
            print('=' * 30)
            print('Running "%s"...' % function_name)
            print('=' * 30)
            func = globals()[function_name]
            func()


def populate_thesaurus_database():
    from lex.oed.thesaurus.thesaurusdb import store_taxonomy, store_content
    store_taxonomy()
    store_content()


def bayes_classifier():
    from bayes.bayesclassifier import BayesClassifier
    bc = BayesClassifier(resources_dir=config.RESOURCES_DIR)
    bc.store_features_by_sense()
    bc.build_rank_files()
    bc.make_classifiers()
    bc.classify_new_senses()


def bayes_compounds():
    from compounds.bayescompounds import BayesCompounds
    bc = BayesCompounds(resources_dir=config.RESOURCES_DIR)
    bc.make_classifiers()
    bc.classify_new_senses(bias_last=1.2, dir='bias_low')
    bc.classify_new_senses(bias_last=1.6, dir='bias_high')
    bc.classify_new_senses(dir='bias_neutral')


def index_compounds():
    from compounds.indexer.rawindexer import make_raw_index
    from compounds.indexer.refiner import refine_index
    make_raw_index(config.CLASSIFIED_DIR)
    refine_index()


def index_binomials():
    from resources.binomials import Binomials
    bnm = Binomials(input_dir=config.CLASSIFIED_DIR,
                    resources_dir=config.RESOURCES_DIR,)
    bnm.make_raw_index()
    bnm.refine_genera_index()
    bnm.refine_binomial_index()


def index_main_senses():
    from resources.mainsense.mainsensecompiler import MainSenseCompiler
    msc = MainSenseCompiler(input_dir=config.CLASSIFIED_DIR,
                            resources_dir=config.RESOURCES_DIR,)
    msc.make_raw_index()
    msc.refine_index()
    msc.finalize()


def index_superordinates():
    from resources.superordinates.superordinateindexer import SuperordinateIndexer
    from lex.oed.thesaurus.dbbackend.populator import store_superordinates
    si = SuperordinateIndexer(
        input_dir=config.CLASSIFIED_DIR,
        output_dir=os.path.join(config.RESOURCES_DIR, 'superordinates'),
    )
    si.compile_index()
    si.refine_index()
    store_superordinates(os.path.join(config.RESOURCES_DIR, 'superordinates'))


def store_classified():
    from pickler.sensemanager import SensePickler
    sp = SensePickler(mode='classified',
                      output_dir=config.CLASSIFIED_DIR,
                      resources_dir=config.RESOURCES_DIR)
    sp.pickle_senses()


def store_unclassified():
    from pickler.sensemanager import SensePickler
    sp = SensePickler(mode='unclassified',
                      output_dir=config.UNCLASSIFIED_DIR,
                      resources_dir=config.RESOURCES_DIR)
    sp.pickle_senses()


def test_sense_parser():
    """
    Like store_classified() and store_unclassified(), but doesn't save
    the output - use for testing only.
    Note this this parses both classified and unclassified senses.
    """
    from pickler.sensemanager import SensePickler
    sp = SensePickler(mode='both',
                      output_dir=None,
                      resources_dir=config.RESOURCES_DIR,)
    sp.pickle_senses()


def reset_db():
    from lex.oed.thesaurus.thesaurusdb import reset
    reset()


def test_classifier():
    from classifyengine.classifier import Classifier
    cl = Classifier(iteration=1,
                    input_dir=config.UNCLASSIFIED_DIR,
                    output_dir=None,
                    resources_dir=config.RESOURCES_DIR,
                    mode='test',)
    cl.classify()


def classify1():
    from classifyengine.classifier import Classifier
    cl = Classifier(iteration=1,
                    input_dir=config.UNCLASSIFIED_DIR,
                    output_dir=config.ITERATION1_DIR,
                    resources_dir=config.RESOURCES_DIR,)
    cl.prepare_output_directories()
    cl.classify()


def update_db():
    from processes.dbupdater import DbUpdater
    dbu = DbUpdater(
        input_dir=os.path.join(config.ITERATION1_DIR, 'classified'),
    )
    dbu.update()


def classify2():
    from classifyengine.classifier import Classifier
    cl = Classifier(iteration=2,
                    input_dir=os.path.join(config.ITERATION1_DIR, 'unclassified'),
                    output_dir=config.ITERATION2_DIR,
                    resources_dir=config.RESOURCES_DIR,)
    cl.prepare_output_directories()
    cl.classify()


def statistics():
    from processes.statistics import Statistics
    stats = Statistics(
        directories=[config.ITERATION1_DIR, config.ITERATION2_DIR, ]
    )
    stats.compile_stats()


def populate_json():
    from websitedb.makejson import populate_taxonomy, populate_senses
    populate_taxonomy(out_dir=os.path.join(config.JSON_DIR, 'taxonomy'),)
    populate_senses(input=[config.ITERATION1_DIR, config.ITERATION2_DIR, ],
                    out_dir=os.path.join(config.JSON_DIR, 'senses'), )


def random_sample():
    from processes.randomsampler import RandomSampler
    rs = RandomSampler(
        directories=[config.ITERATION1_DIR, config.ITERATION2_DIR, ],
        out_dir=config.SAMPLES_DIR,
    )
    rs.iterate()


if __name__ == '__main__':
    dispatch()
