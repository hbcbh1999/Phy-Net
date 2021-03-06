
import numpy as np

def divergence_2d(velocity_field):

  velocity_field_x_0 = velocity_field[0:-2,1:-1,1]
  velocity_field_x_2 = velocity_field[2:,1:-1,1]

  velocity_field_y_0 = velocity_field[1:-1,0:-2,0]
  velocity_field_y_2 = velocity_field[1:-1,2:,0]

  div = (velocity_field_x_0 - velocity_field_x_2) + (velocity_field_y_0 - velocity_field_y_2)

  return div

def divergence_3d(velocity_field):

  velocity_field_x_0 = velocity_field[0:-2,1:-1,1:-1,2]
  velocity_field_x_2 = velocity_field[2:,1:-1,1:-1,2]

  velocity_field_y_0 = velocity_field[1:-1,0:-2,1:-1,1]
  velocity_field_y_2 = velocity_field[1:-1,2:,1:-1,1]

  velocity_field_z_0 = velocity_field[1:-1,1:-1,0:-2,0]
  velocity_field_z_2 = velocity_field[1:-1,1:-1,2:,0]

  div = (velocity_field_x_0 - velocity_field_x_2) + (velocity_field_y_0 - velocity_field_y_2) + (velocity_field_z_0 - velocity_field_z_2)

  return div




