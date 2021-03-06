
"""Builds the ring network.

Summary of available functions:

  # Compute pics of the simulation runnig.
  
  # Create a graph to train on.
"""


import tensorflow as tf
import numpy as np
from nn import *
import input.ring_net_input as ring_net_input
import systems.fluid_createTFRecords as fluid
import systems.em_createTFRecords as em

FLAGS = tf.app.flags.FLAGS

# Constants describing the training process.

################# system params
tf.app.flags.DEFINE_string('system', 'fluid_flow',
                           """ system to compress """)
tf.app.flags.DEFINE_integer('lattice_size', 9,
                           """ size of lattice """)
tf.app.flags.DEFINE_string('dimensions', '256x256',
                           """ dimension of simulation with x between value """)

################# running params
tf.app.flags.DEFINE_string('base_dir', '../checkpoints',
                            """dir to store trained net """)
tf.app.flags.DEFINE_bool('restore', True,
                            """ restore model if there is one """)

################# model params
## resnet params
tf.app.flags.DEFINE_integer('nr_residual', 2,
                           """ number of residual blocks before down sizing """)
tf.app.flags.DEFINE_integer('nr_downsamples', 4,
                           """ numper of downsamples """)
tf.app.flags.DEFINE_string('nonlinearity', "relu",
                           """ what nonlinearity to use, leakey_relu, relu, elu, concat_elu """)
tf.app.flags.DEFINE_float('keep_p', 1.0,
                           """ keep probability for res blocks """)
tf.app.flags.DEFINE_bool('gated', False,
                           """ gated res blocks """)
tf.app.flags.DEFINE_integer('filter_size', 16,
                           """ filter size for first res block. the rest of the filters are 2x every downsample """)
## compression params
tf.app.flags.DEFINE_bool('lstm', False,
                           """ lstm or non recurrent""")
tf.app.flags.DEFINE_integer('nr_residual_compression', 3,
                           """ number of residual compression layers """)
tf.app.flags.DEFINE_integer('filter_size_compression', 128,
                           """ filter size for compression piece """)
## gan params (currently not in use)
tf.app.flags.DEFINE_bool('gan', False,
                           """ use gan training """)
tf.app.flags.DEFINE_integer('nr_discriminators', 1,
                           """ number of discriminators to train """)
tf.app.flags.DEFINE_integer('z_size', 50,
                           """ size of z vector """)
tf.app.flags.DEFINE_integer('nr_residual_discriminator', 1,
                           """ number of residual blocks before down sizing """)
tf.app.flags.DEFINE_integer('nr_downsamples_discriminator', 3,
                           """ numper of downsamples """)
tf.app.flags.DEFINE_float('keep_p_discriminator', 1.0,
                           """ keep probability for res blocks """)
tf.app.flags.DEFINE_integer('filter_size_discriminator', 32,
                           """ filter size for first res block of discriminator """)
tf.app.flags.DEFINE_integer('lstm_size_discriminator', 512,
                           """ size of lstm cell in discriminator """)

################# optimize params
tf.app.flags.DEFINE_string('optimizer', "adam",
                           """ what optimizer to use (currently adam is the only option)""")
tf.app.flags.DEFINE_float('reconstruction_lr', 0.0004,
                           """ learning rete for reconstruction """)
tf.app.flags.DEFINE_float('gan_lr', 2e-5,
                           """ learning rate for training gan """)
tf.app.flags.DEFINE_float('lambda_divergence', 0.2,
                           """ weight of divergence or gradient differnce error """)

################# train params
tf.app.flags.DEFINE_integer('max_steps', 1000000,
                            """ max steps to train """)
tf.app.flags.DEFINE_integer('unroll_length', 5,
                           """ unroll length """)
tf.app.flags.DEFINE_integer('init_unroll_length', 0,
                           """ inital unroll length before training """)
tf.app.flags.DEFINE_bool('unroll_from_true', False,
                           """ use the true data when unrolling the network (probably just used for unroll_length 1 when doing curriculum learning""")
tf.app.flags.DEFINE_integer('batch_size', 4,
                           """ batch size """)
tf.app.flags.DEFINE_integer('nr_gpus', 1,
                           """ number of gpus for training (each gpu with have batch size FLAGS.batch_size""")
tf.app.flags.DEFINE_bool('tf_store_images', False,
                           """ store the velocity images in tensorboard (makes checkpoints waaaaay to big) """)

################# test params
tf.app.flags.DEFINE_bool('train', True,
                           """ train or test """)
tf.app.flags.DEFINE_string('test_dimensions', '256x256',
                           """ test video dimentions """)
tf.app.flags.DEFINE_integer('video_length', 200,
                           """ video dimentions """)
tf.app.flags.DEFINE_integer('test_length', 50,
                           """ sequence length for testing (making error plots) """)
tf.app.flags.DEFINE_integer('test_nr_runs', 50,
                           """ number of simulations to test on (making error plots) """)
tf.app.flags.DEFINE_integer('test_nr_per_simulation', 1,
                           """ number of test runs per simulations (making error plots) """)

####### inputs #######
def inputs(empty=False, name="inputs", shape=None):
  """makes input vector
  Args:
    empty will just return an empty state to fill with a feed dict
  Return:
    x: input vector, may be filled 
  """
  if shape is None:
    shape = FLAGS.dimensions.split('x')
    shape = map(int, shape)
  frame_num = FLAGS.lattice_size # 3 for 2D and 4 for 3D (this will change with mag stuff)
  if empty:
    #state = tf.placeholder(tf.float32, [FLAGS.batch_size, FLAGS.unroll_length] + shape + [frame_num], name=name)
    #boundary = tf.placeholder(tf.float32, [FLAGS.batch_size, 1] + shape + [1], name=name)
    state = tf.placeholder(tf.float32, [1] + shape + [frame_num], name=name)
    boundary = tf.placeholder(tf.float32, [1] + shape + [1], name=name)
  elif FLAGS.system == "fluid_flow":
    state, boundary = ring_net_input.fluid_inputs(FLAGS.batch_size, FLAGS.init_unroll_length + FLAGS.unroll_length, shape, frame_num, FLAGS.train)
  elif FLAGS.system == "em":
    state, boundary = ring_net_input.em_inputs(FLAGS.batch_size, FLAGS.init_unroll_length + FLAGS.unroll_length, shape, frame_num, FLAGS.train)
 
  if FLAGS.gan:
    z = tf.placeholder("float", [None, total_unroll_length, FLAGS.z_size])
    return state, boundary, z
  else:
    return state, boundary

####### feed_dict #######
def feed_dict(seq_length, shape, frame_num, run_number, start_index):
  """makes feed dict for testing
  """
  if FLAGS.system == "fluid_flow":
    dir_name = "fluid_flow_"
    if len(shape) == 2:
      dir_name = dir_name + str(shape[0]) + 'x' + str(shape[1]) + '_test'
    else:
      dir_name = dir_name + str(shape[0]) + 'x' + str(shape[1]) + 'x' + str(shape[2]) + '_test'
    state, boundary = fluid.generate_feed_dict(seq_length, shape, frame_num, dir_name, run_number, start_index)
  elif FLAGS.system == "em":
    dir_name = "em_"
    if len(shape) == 2:
      dir_name = dir_name + str(shape[0]) + 'x' + str(shape[1]) + '_test'
    else:
      dir_name = dir_name + str(shape[0]) + 'x' + str(shape[1]) + 'x' + str(shape[2]) + '_test'
    state, boundary = em.generate_feed_dict(seq_length, shape, frame_num, dir_name, run_number, start_index)
 
  return state, boundary

####### rand_feed_dict #######
def rand_feed_dict(shape=None):
  """makes feed dict for testing
  """
  if shape is None:
    shape = FLAGS.dimensions.split('x')
    shape = map(int, shape)
  frame_num = FLAGS.lattice_size # 3 for 2D and 4 for 3D (this will change with mag stuff)
  if FLAGS.system == "fluid_flow":
    dir_name = 'fluid_flow_' + str(shape[0]) + 'x' + str(shape[1]) + '_'
    if len(shape) == 3:
      dir_name = dir_name + str(shape[2]) + '_'
    state, boundary = fluid.generate_random_feed_dict(FLAGS.batch_size, FLAGS.unroll_length, shape, frame_num, dir_name)
  elif FLAGS.system == "em":
    dir_name = 'em_' + str(shape[0]) + 'x' + str(shape[1]) + '_'
    if len(shape) == 3:
      dir_name = dir_name + str(shape[2]) + '_'
    state, boundary = em.generate_random_feed_dict(FLAGS.batch_size, FLAGS.unroll_length, shape, frame_num, dir_name)
 
  return state, boundary


####### encoding #######
def encoding(inputs, name='', boundary=False):
  """Builds encoding part of ring net.
  Args:
    inputs: input to encoder
    keep_prob: dropout layer
  """
  #--------- Making the net -----------
  # x_1 -> y_1 -> y_2 -> x_2
  # this peice x_1 -> y_1
  x_i = inputs

  nonlinearity = set_nonlinearity(FLAGS.nonlinearity)

  for i in xrange(FLAGS.nr_downsamples):

    filter_size = FLAGS.filter_size*(pow(2,i))
    print("filter size for layer " + str(i) + " of encoding is " + str(filter_size) + " with shape " + str(x_i.get_shape()))

    x_i = res_block(x_i, filter_size=filter_size, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=2, gated=FLAGS.gated, name=name + "resnet_down_sampled_" + str(i) + "_nr_residual_0", begin_nonlinearity=False) 


    for j in xrange(FLAGS.nr_residual - 1):
      x_i = res_block(x_i, filter_size=filter_size, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=1, gated=FLAGS.gated, name=name + "resnet_down_sampled_" + str(i) + "_nr_residual_" + str(j+1))

  if boundary:
    x_i = res_block(x_i, filter_size=FLAGS.filter_size_compression*2, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=1, gated=FLAGS.gated, name=name + "resnet_last_before_compression")
  else:
    x_i = res_block(x_i, filter_size=FLAGS.filter_size_compression, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=1, gated=FLAGS.gated, name=name + "resnet_last_before_compression")

  return x_i
####### encoding template #######
encode_state_template = tf.make_template('encode_state_template', encoding)
encode_boundary_template = tf.make_template('encode_boundary_template', encoding)
#################################

####### compression #############
def compression(y):
  """Builds compressed dynamical system part of the net.
  Args:
    inputs: input to system
    keep_prob: dropout layer
  """
  #--------- Making the net -----------
  # x_1 -> y_1 -> y_2 -> x_2
  # this peice y_1 -> y_2

  y_i = y

  nonlinearity = set_nonlinearity(FLAGS.nonlinearity)

  for i in xrange(FLAGS.nr_residual_compression):
    #print("resnet compression " + str(i))
    y_i = res_block(y_i, filter_size=FLAGS.filter_size_compression, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=1, gated=FLAGS.gated, name="resnet_compression_" + str(i))

  return y_i
####### compression template ######
compress_template = tf.make_template('compress_template', compression)
#################################

''' # not functional yet!!!
def compression_lstm(y, hidden_state=None):
  """Builds compressed dynamical system part of the net.
  Args:
    inputs: input to system
    keep_prob: dropout layer
  """
  #--------- Making the net -----------
  # x_1 -> y_1 -> y_2 -> x_2
  # this peice y_1 -> y_2

  y_i = y

  if hidden_state is not None:
    hidden_state_1_i = hidden_state[0] 
    hidden_state_2_i = hidden_state[1]

  hidden_state_1_i_new = []
  hidden_state_2_i_new = []

  if FLAGS.multi_resolution:
    for i in xrange(FLAGS.nr_downsamples):
      hidden_state_1_i_j_new = []
      hidden_state_2_i_j_new = []
      y_i_new = []
      for j in xrange(FLAGS.nr_residual_compression):
        if hidden is not None:
          y_i, hidden_state_1_store, hidden_state_2_store = res_block_lstm(y_i, hidden_state_1_i[i][j], hidden_state_2_i[i][j], FLAGS.keep_p, name="resnet_downsampled_" + str(i) + "_resnet_lstm_" + str(j))
        else:
          y_i, hidden_state_1_store, hidden_state_2_store = res_block_lstm(y_i, None, None, FLAGS.keep_p, name="resnet_downsampled_" + str(i) + "_resnet_lstm_" + str(j))
        hidden_state_1_i_j_new.append(hidden_state_1_store)
        hidden_state_2_i_j_new.append(hidden_state_2_store)
      hidden_state_1_i_new.append(hidden_state_1_i_j_new) 
      hidden_state_2_i_new.append(hidden_state_2_i_j_new) 

  else:
    for i in xrange(FLAGS.nr_residual_compression):
      if hidden is not None:
        y_i, hidden_state_1_store, hidden_state_2_store = res_block_lstm(y_i, hidden_state_1_i[i], hidden_state_2_i[i], FLAGS.keep_p, name="resnet_lstm_" + str(i))
      else:
        y_i, hidden_state_1_store, hidden_state_2_store = res_block_lstm(y_i, None, None, FLAGS.keep_p, name="resnet_lstm_" + str(i))
      hidden_state_1_i_new.append(hidden_state_1_store)
      hidden_state_2_i_new.append(hidden_state_2_store)

  hidden = [hidden_state_1_i_new, hidden_state_2_i_new]

  return y_i, hidden 
'''

####### decoding #######
def decoding(y):
  """Builds decoding part of ring net.
  Args:
    inputs: input to decoder
  """
  #--------- Making the net -----------
  # x_1 -> y_1 -> y_2 -> x_2
  # this peice y_2 -> x_2
  y_i = y
 
  nonlinearity = set_nonlinearity(FLAGS.nonlinearity)

  for i in xrange(FLAGS.nr_downsamples-1):
    filter_size = FLAGS.filter_size*pow(2,FLAGS.nr_downsamples-i-2)
    print("decoding filter size for layer " + str(i) + " of encoding is " + str(filter_size))
    y_i = transpose_conv_layer(y_i, 4, 2, filter_size, "up_conv_" + str(i))

    for j in xrange(FLAGS.nr_residual):
      y_i = res_block(y_i, filter_size=filter_size, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p, stride=1, gated=FLAGS.gated, name="resnet_up_sampled_" + str(i) + "_nr_residual_" + str(j+1))

  y_i = transpose_conv_layer(y_i, 4, 2, FLAGS.lattice_size, "up_conv_" + str(FLAGS.nr_downsamples))

  return tf.nn.tanh(y_i)
####### decoding template #######
decoding_template = tf.make_template('decoding_template', decoding)
#################################

'''
CURRENTLY NOT IN USE
def add_z(y, z):
  y_shape = int_shape(y) 
  z = fc_layer(z, y_shape[1]*y_shape[2], "fc_z_" + str(i))
  z = tf.reshape(z, [-1, y_shape[1], y_shape[2], 1])
  z = conv_layer(z, 3, 1, y_shape[3], "conv_z_" + str(i))
  y_new = y + z

  return y_new

def discriminator(output, hidden_state=None):

  x_i = output

  nonlinearity = set_nonlinearity(FLAGS.nonlinearity)

  label = []

  for split in xrange(FLAGS.nr_discriminators):
    for i in xrange(FLAGS.nr_downsamples):
      filter_size = FLAGS.filter_size_discriminator*pow(2,i)
      #print("filter size for discriminator layer " + str(i) + " of encoding is " + str(filter_size))
      x_i = res_block(x_i, filter_size=filter_size, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p_discriminator, stride=2, gated=FLAGS.gated, name="discriminator_" + str(split) + "_resnet_discriminator_down_sampled_" + str(i) + "_nr_residual_0") 
      for j in xrange(FLAGS.nr_residual - 1):
        x_i = res_block(x_i, filter_size=filter_size, nonlinearity=nonlinearity, keep_p=FLAGS.keep_p_discriminator, stride=1, gated=FLAGS.gated, name="discriminator_" + str(split) + "_resnet_discriminator_" + str(i) + "_nr_residual_" + str(j+1))
  
    with tf.variable_scope("discriminator_LSTM_" + str(split), initializer = tf.random_uniform_initializer(-0.01, 0.01)):
      lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(FLAGS.lstm_size_discriminator, forget_bias=1.0)
      if hidden_state == None:
        batch_size = x_i.get_shape()[0]
        hidden_state = lstm_cell.zero_state(batch_size, tf.float32)
  
      x_i, new_state = lstm_cell(x_i, hidden_state)

      x_i = fc_layer(x_i, 1, "discriminator_fc_" + str(split), False, True)
  
      label.append(x_i)

  label = tf.pack(label)

  return label
'''

####### unroll #######
def unroll(state, boundary, z=None):

  total_unroll_length = FLAGS.init_unroll_length + FLAGS.unroll_length 
 
  if FLAGS.lstm:
    # need to implement
    exit()
  else:
    # store all out
    x_out = []
    # encode
    y_1 = encode_state_template(state[:,0])
    small_boundary = encode_boundary_template(boundary[:,0], name='boundry_', boundary=True)
    # apply boundary
    [small_boundary_mul, small_boundary_add] = tf.split(small_boundary, 2, len(small_boundary.get_shape())-1)
    y_1 = (small_boundary_mul * y_1) + small_boundary_add
    # add z if gan training
    if FLAGS.gan:
      y_1 = add_z(y_1, z)
    # unroll all
    for i in xrange(FLAGS.unroll_length):
      # set reuse to true (not for new tensorflow)
      #if i > 0:
      #  tf.get_variable_scope().reuse_variables()
        
      # decode and add to list
      x_2 = decoding_template(y_1)
      #x_2 = x_2 * (1.0-boundary[:,0]) # kill grads on boundary
      #x_2 = decoding(y_1)
      x_out.append(x_2)
      # display
      # dispay images
      if FLAGS.tf_store_images: # currently not functional
        if len(x_2.get_shape()) == 4:
          tf.summary.image('generated_x_' + str(i), x_2[:,:,:,0:1])
          tf.summary.image('generated_y_' + str(i), x_2[:,:,:,1:2])
          tf.summary.image('generated_density_' + str(i), x_2[:,:,:,2:3])
        elif len(x_2.get_shape()) == 5:
          tf.summary.image('generated_x_' + str(i), x_2[:,int(x_2.get_shape()[1])/2,:,:,0:1])
          tf.summary.image('generated_y_' + str(i), x_2[:,int(x_2.get_shape()[1])/2,:,:,1:2])
          tf.summary.image('generated_z_' + str(i), x_2[:,int(x_2.get_shape()[1])/2,:,:,2:3])
          tf.summary.image('generated_density_' + str(i), x_2[:,int(x_2.get_shape()[1])/2,:,:,3:4])

      # compression
      #y_1 = compression(y_1)
      if FLAGS.unroll_length > 1:
        y_1 = compress_template(y_1)
        # boundary
        y_1 = (small_boundary_mul * y_1) + small_boundary_add
        # add z if gan training
        if FLAGS.gan:
          y_1 = add_z(y_1, z)

  x_out = tf.stack(x_out)
  perm = np.concatenate([np.array([1,0]), np.arange(2,len(x_2.get_shape())+1,1)], 0)
  print(perm)
  x_out = tf.transpose(x_out, perm=perm)
  return x_out
####### unroll template #######
unroll_template = tf.make_template('unroll_template', unroll)
###############################

####### continual unroll #######
def continual_unroll(state, boundary, z=None):

  if FLAGS.lstm:
    # need to implement
    exit()
  else:
    # store all out
    y_1 = encode_state_template(state)
    small_boundary = encode_boundary_template(boundary, name='boundry_', boundary=True)
    # apply boundary
    [small_boundary_mul, small_boundary_add] = tf.split(small_boundary, 2, len(small_boundary.get_shape())-1)
    y_1_boundary = (small_boundary_mul * y_1) + small_boundary_add
    # add z if gan training
    if FLAGS.gan:
      y_1_boundary = add_z(y_1_boundary, z)
    # unroll all
    x_2 = decoding_template(y_1_boundary)
    if FLAGS.unroll_length > 1:
      y_2 = compress_template(y_1_boundary)
    else:
      y_2 = None

  return y_1, small_boundary_mul, small_boundary_add, x_2, y_2
####### continual unroll template #######
continual_unroll_template = tf.make_template('unroll_template', continual_unroll) # same variable scope as unroll_template
#########################################

