import json
import metapy
import os
import pytoml
import requests
import tempfile
import unittest

from tqdm import *
from timeout import Timeout
from classify import make_classifier


class TestClassifier(unittest.TestCase):
    cfgs = [
        '/data/cs410/mp3/twitter-geo-withheld/config.toml'
    ]
    submission_url = 'http://10.0.0.12/api'

    def get_results(self, cfg_file):
        # Ugly hack: replace analyzers configuration with user's analyzer
        # configuration

        with open('config.toml') as user_cfg:
            user_conf = pytoml.load(user_cfg)

        with open(cfg_file) as data_cfg:
            data_conf = pytoml.load(data_cfg)

        data_conf['analyzers'] = user_conf['analyzers']

        with tempfile.NamedTemporaryFile(mode='w+') as final_cfg:
            pytoml.dump(data_conf, final_cfg)
            final_cfg.flush()

            inv_idx = metapy.index.make_inverted_index(final_cfg.name)
            fwd_idx = metapy.index.make_forward_index(final_cfg.name)

        dset = metapy.classify.MulticlassDataset(fwd_idx)
        train_view = dset[0:5473]
        test_view = dset[5473:]

        classifier = make_classifier(train_view, inv_idx, fwd_idx)
        return [classifier.classify(inst.weights) for inst in test_view]

    def test_upload_submission(self):
        metapy.log_to_stderr()

        """
        This is the unit test that actually submits the results to the
        leaderboard. If there is an error (on either end of the submission),
        the unit test is failed, and the failure string is also reproduced
        on the leaderboard.
        """
        req = {
            'token': os.environ.get('GITLAB_API_TOKEN'),
            'alias': os.environ.get('COMPETITION_ALIAS') or 'Anonymous',
            'results': []
        }

        for cfg_file in self.cfgs:
            res = {'error': None}
            with open(cfg_file, 'r') as fin:
                cfg_d = pytoml.load(fin)
            res['dataset'] = cfg_d['dataset']
            print("\nRunning on {}...".format(res['dataset']))
            timeout_len = cfg_d['timeout']

            try:
                with Timeout(timeout_len):
                    res['results'] = self.get_results(cfg_file)
            except Timeout.Timeout:
                error_msg = "Timeout error: {}s".format(timeout_len)
                res['error'] = error_msg
                res['results'] = []

            req['results'].append(res)

        response = requests.post(self.submission_url, json=req)
        jdata = response.json()
        print(jdata)
        self.assertTrue(jdata['submission_success'])


if __name__ == '__main__':
    unittest.main()
