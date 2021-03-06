# example python script for loading spikefinder data
#
# for more info see https://github.com/codeneuro/spikefinder
#
# requires numpy, pandas, matplotlib
#

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

calcium_train = []
calcium_test = []
spikes_train = []
ids = []
ids_test = []

for dataset in range(10):
    calcium_train.append(np.array(pd.read_csv('spikefinder.train/'+str(dataset+1) + '.train.calcium.csv')))
    if dataset < 5:
        calcium_test.append(np.array(pd.read_csv('spikefinder.test/'+str(dataset+1) + '.test.calcium.csv')))
        ids_test.append(np.array([dataset]*calcium_test[-1].shape[1]))
    spikes_train.append(np.array(pd.read_csv('spikefinder.train/'+str(dataset+1) + '.train.spikes.csv')))
    ids.append(np.array([dataset]*calcium_train[-1].shape[1]))
lens = np.array([c.shape[0] for c in calcium_train])
lens_test = np.array([c.shape[0] for c in calcium_test])
maxlen = max(lens)
maxlen_test = max(lens_test)
calcium_train_padded = np.hstack([np.pad(c,((0,maxlen-c.shape[0]),(0,0)),'constant',constant_values=np.nan) for c in calcium_train])
calcium_test_padded = np.hstack([np.pad(c,((0,maxlen_test-c.shape[0]),(0,0)),'constant',constant_values=np.nan) for c in calcium_test])
spikes_train_padded = np.hstack([np.pad(c,((0,maxlen-c.shape[0]),(0,0)),'constant',constant_values=np.nan) for c in spikes_train])
ids_stacked = np.hstack(ids)
ids_test_stacked = np.hstack(ids_test)
calcium_train_padded[spikes_train_padded<-1] = np.nan
spikes_train_padded[spikes_train_padded<-1] = np.nan

calcium_train_padded[np.isnan(calcium_train_padded)] = 0.
spikes_train_padded[np.isnan(spikes_train_padded)] = -1.

calcium_train_padded = calcium_train_padded.T[:,:,np.newaxis]
calcium_test_padded = calcium_test_padded.T[:,:,np.newaxis]
spikes_train_padded = spikes_train_padded.T[:,:,np.newaxis]

ids_onehot = np.zeros((calcium_train_padded.shape[0],calcium_train_padded.shape[1],10))
ids_onehot_test = np.zeros((calcium_test_padded.shape[0],calcium_test_padded.shape[1],10))
for n,i in enumerate(ids_stacked):
    ids_onehot[n,:,i] = 1.

for n,i in enumerate(ids_test_stacked):
    ids_onehot_test[n,:,i] = 1.

from keras.models import Sequential, Model
from keras.layers.core import Masking
from keras.layers.merge import Concatenate
from keras.layers import Dense, Activation, Dropout, Input
from keras.layers.convolutional import Conv1D
from keras.layers.normalization import BatchNormalization

from keras import backend as K
import tensorflow as tf


main_input = Input(shape=(None,1), name='main_input')
dataset_input = Input(shape=(None,10), name='dataset_input')
x = Conv1D(10,300,padding='same',input_shape=(None,1))(main_input)
x = Activation('tanh')(x)
x = Dropout(0.1)(x)
x = Conv1D(5,10,padding='same')(x)
x = Activation('relu')(x)
x = Concatenate()([x,dataset_input])
x = Dropout(0.1)(x)
x = Conv1D(10,1,padding='same')(x)
x = Activation('relu')(x)
x = Dropout(0.1)(x)
x = Conv1D(10,5,padding='same')(x)
x = Activation('relu')(x)
x = Dropout(0.1)(x)
x = Conv1D(10,5,padding='same')(x)
x = Activation('relu')(x)
x = Dropout(0.1)(x)
x = Conv1D(1,5,padding='same')(x)
output = Activation('sigmoid')(x)

model = Model(inputs=[main_input,dataset_input],outputs=output)

def pearson_corr(y_true, y_pred,
        pool=True):
    """Calculates Pearson correlation as a metric.
    This calculates Pearson correlation the way that the competition calculates
    it (as integer values).
    y_true and y_pred have shape (batch_size, num_timesteps, 1).
    """

    if pool:
        y_true = pool1d(y_true, length=4)
        y_pred = pool1d(y_pred, length=4)

    mask = tf.to_float(y_true>=0.)
    samples = K.sum(mask,axis=1,keepdims=True)
    x_mean = y_true - K.sum(mask*y_true, axis=1, keepdims=True)/samples
    y_mean = y_pred - K.sum(mask*y_pred, axis=1, keepdims=True)/samples

    # Numerator and denominator.
    n = K.sum(x_mean * y_mean * mask, axis=1)
    d = (K.sum(K.square(x_mean)* mask, axis=1) *
         K.sum(K.square(y_mean)* mask, axis=1))

    return 1.-K.mean(n / (K.sqrt(d) + 1e-12))

def pool1d(x, length=4):
    """Adds groups of `length` over the time dimension in x.
    Args:
        x: 3D Tensor with shape (batch_size, time_dim, feature_dim).
        length: the pool length.
    Returns:
        3D Tensor with shape (batch_size, time_dim // length, feature_dim).
    """

    x = tf.expand_dims(x, -1)  # Add "channel" dimension.
    avg_pool = tf.nn.avg_pool(x,
        ksize=(1, length, 1, 1),
        strides=(1, length, 1, 1),
        padding='SAME')
    x = tf.squeeze(avg_pool, axis=-1)

    return x * length

model.compile(loss=pearson_corr,optimizer='adam')
model.load_weights('convnet')
pred_train = model.predict([calcium_train_padded,ids_onehot])
pred_test = model.predict([calcium_test_padded,ids_onehot_test])

for dataset in range(10):
    pd.DataFrame(pred_train[ids_stacked == dataset,:calcium_train[dataset].shape[0]].squeeze().T).to_csv('out_spikenet-3/'+str(dataset+1)+'.train.spikes.csv',sep=',',index=False)
    if dataset < 5:
        pd.DataFrame(pred_test[ids_test_stacked == dataset,:calcium_test[dataset].shape[0]].squeeze().T).to_csv('out_spikenet-3/'+str(dataset+1)+'.test.spikes.csv',sep=',',index=False)
