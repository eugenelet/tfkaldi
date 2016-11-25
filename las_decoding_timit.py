# fix some pylint stuff
# fixes the np.random error
# pylint: disable=E1101
# fixes the unrecognized state_is_tuple
# pylint: disable=E1123
# fix the pylint import problem.
# pylint: disable=E0401

import time
import pickle
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from processing.batch_dispenser import PhonemeBatchDispenser
from processing.target_normalizers import timit_phone_norm
from processing.target_coder import PhonemeEncoder
from processing.feature_reader import FeatureReader
from neuralnetworks.classifiers.las_model import LasModel
from neuralnetworks.classifiers.las_model import GeneralSettings
from neuralnetworks.classifiers.las_model import ListenerSettings
from neuralnetworks.decoder import LasDecoder
from IPython.core.debugger import Tracer; debug_here = Tracer();


def set_up_dispensers(max_batch_size):
    """load training, validation and testing data.""" 

    #training data --------------------------------------------------------
    timit_path = "/esat/spchtemp/scratch/moritz/dataSets/timit/s5/"
    feature_path = timit_path  + "fbank/" + "raw_fbank_train.1.scp"
    cmvn_path = None
    utt2spk_path = timit_path + "data/train/utt2spk"
    feature_reader = FeatureReader(feature_path, cmvn_path, utt2spk_path,
                                   0, MAX_TIME_STEPS_TIMIT)
    train_phone_path = timit_path + "data/train/train39.text"
    target_coder = PhonemeEncoder(timit_phone_norm) 
    target_path = train_phone_path
    #self, feature_reader, target_coder, size, target_path

    traindispenser = PhonemeBatchDispenser(feature_reader, target_coder, max_batch_size, 
                                           target_path)

    #validation data ------------------------------------------------------
    feature_path = timit_path  + "fbank/" + "raw_fbank_dev.1.scp"
    cmvn_path = None
    utt2spk_path = timit_path + "data/dev/utt2spk"
    feature_reader = FeatureReader(feature_path, cmvn_path, utt2spk_path,
                                   0, MAX_TIME_STEPS_TIMIT)
    train_phone_path = timit_path + "data/dev/dev39.text"
    target_coder = PhonemeEncoder(timit_phone_norm) 
    target_path = train_phone_path
    #self, feature_reader, target_coder, size, target_path

    valdispenser = PhonemeBatchDispenser(feature_reader, target_coder, max_batch_size, 
                                         target_path)

    #######test data-------------------------------------------------------
    feature_path = timit_path  + "fbank/" + "raw_fbank_test.1.scp"
    cmvn_path = None
    utt2spk_path = timit_path + "data/test/utt2spk"
    feature_reader = FeatureReader(feature_path, cmvn_path, utt2spk_path,
                                   0, MAX_TIME_STEPS_TIMIT)
    train_phone_path = timit_path + "data/test/test39.text"
    target_coder = PhonemeEncoder(timit_phone_norm) 
    target_path = train_phone_path
    #self, feature_reader, target_coder, size, target_path

    testdispenser = PhonemeBatchDispenser(feature_reader, target_coder, max_batch_size, 
                                          target_path)
    return traindispenser, valdispenser, testdispenser

start_time = time.time()

###Learning Parameters
LEARNING_RATE = 0.0008
#LEARNING_RATE = 0.0001
LEARNING_RATE_DECAY = 0.98

OVERFIT_TOL = 99999

####Network Parameters
n_features = 40

TIMIT_LABELS = 39
CTC_TIMIT_LABELS = TIMIT_LABELS + 1 #add one for ctc

if 1:
    epoch_loss_lst, epoch_loss_lst_val, test_loss, LEARNING_RATE, \
    LEARNING_RATE_DECAY, epoch, UTTERANCES_PER_MINIBATCH, \
    general_settings, listener_settings, attend_and_spell_settings = \
    pickle.load(open("saved_models/promising_las_timit_0.001_96_2/2016-11-25.pkl", "rb"))
else:
    #molder
    MAX_N_EPOCHS = 600
    MAX_BATCH_SIZE = 32
    UTTERANCES_PER_MINIBATCH = 16 #time vs memory tradeoff.
    #mel_feature_no, mini_batch_size, target_label_no, dtype
    general_settings = GeneralSettings(n_features, UTTERANCES_PER_MINIBATCH,
                                       CTC_TIMIT_LABELS, tf.float32)
    #lstm_dim, plstm_layer_no, output_dim, out_weights_std
    listener_settings = ListenerSettings(64, 0, 40, 0.1)

plt.plot(epoch_loss_lst)
plt.plot(epoch_loss_lst_val)
plt.show()
print("Test loss:", test_loss)

MAX_TIME_STEPS_TIMIT = 777
MEL_FEATURE_NO = 40

train_dispenser, val_dispenser, test_dispenser = set_up_dispensers(UTTERANCES_PER_MINIBATCH)

BATCH_COUNT = train_dispenser.num_batches
BATCH_COUNT_VAL = val_dispenser.num_batches
BATCH_COUNT_TEST = test_dispenser.num_batches
print(BATCH_COUNT, BATCH_COUNT_VAL, BATCH_COUNT_TEST)
n_classes = CTC_TIMIT_LABELS

test_batch = test_dispenser.get_batch()
#create the las arcitecture


las_model = LasModel(general_settings, listener_settings,
                     attend_and_spell_settings, decoding=True)

#las_trainer = LasTrainer(las_model, LEARNING_RATE, OMEGA)

max_input_length = np.max([train_dispenser.max_input_length,
                           val_dispenser.max_input_length,
                           test_dispenser.max_input_length])

max_target_length = np.max([train_dispenser.max_target_length,
                            val_dispenser.max_target_length,
                            test_dispenser.max_target_length])

las_decoder = LasDecoder(las_model, MEL_FEATURE_NO, MAX_TIME_STEPS_TIMIT,
                         UTTERANCES_PER_MINIBATCH)


config = tf.ConfigProto()
config.gpu_options.allow_growth = True
with tf.Session(graph=las_decoder.graph, config=config):
    las_decoder.restore(
        'saved_models/promising_las_timit_0.001_96_2/2016-11-25.mdl')
    test_batch = test_dispenser.get_batch()
    #TODO: check input dimension!!! Could be wrong.
    inputs = test_batch[0]
    targets = test_batch[1]
    decoded = las_decoder(inputs)

def greedy_search(network_output):
    """ Extract the largets char probability."""
    utterance_char_batches = []
    for batch in range(0, network_output.shape[0]):
        utterance_chars_nos = []
        for time in range(0, network_output.shape[1]):
            utterance_chars_nos.append(np.argmax(network_output[batch, time, :]))
        utterance_chars = test_dispenser.target_coder.decode(
            utterance_chars_nos)
        utterance_char_batches.append(utterance_chars)
    return np.array(utterance_char_batches)

decoded_targets = greedy_search(decoded)

print(test_dispenser.target_coder.decode(targets[0]))
print(decoded_targets[0])

plt.imshow(decoded[0, :, :])
plt.show()
