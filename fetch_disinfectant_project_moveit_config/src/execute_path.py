#!/usr/bin/env python

import sys
import actionlib
import subprocess
import rospy
import moveit_commander
import moveit_msgs.msg
import numpy as np

from threading import Thread
from moveit_msgs.msg import MoveItErrorCodes, PlanningScene, RobotTrajectory
from moveit_python import MoveGroupInterface, PlanningSceneInterface
from std_msgs.msg import String, Int32, Float32
from geometry_msgs.msg import PoseStamped, Pose, Point, Quaternion, PoseArray

class ExecutePath(object):

  def __init__(self):
    super(ExecutePath, self).__init__()
    # Initialize subscribers
    self.gui_input_sub     = rospy.Subscriber('gui_input', String, self.interface_callback)
    self.waypoints_sub     = rospy.Subscriber('waypoints', PoseArray, self.waypoint_callback)
    self.vel_regulator_sub = rospy.Subscriber('vel_regulator', Float32, self.vel_callback)

    # Publisher
    self.duration_pub  = rospy.Publisher('duration', Float32, queue_size=10)

    # First initialize `moveit_commander`
    moveit_commander.roscpp_initialize(sys.argv)

    # Instantiate a `RobotCommander`_ object. This object is the outer-level
    # interface to the robot
    self.robot = moveit_commander.RobotCommander()

    # Instantiate a `MoveGroupCommander`_ object.  This object is an interface
    # to one group of joints.
    self.group = moveit_commander.MoveGroupCommander("arm_with_torso")
    self.group.set_end_effector_link("ee_link") #use gripper_link if it is planar disinfection

    # We create a `DisplayTrajectory`_ publisher which is used later to publish
    # trajectories for RViz to visualize:
    self.display_trajectory_publisher = rospy.Publisher('/move_group/display_planned_path',
                                                   moveit_msgs.msg.DisplayTrajectory,
                                                   queue_size=20)
    # Initialize waypoints
    self.waypoints = None

    # Initialize missed waypoints
    self.waypoints_missed = None

    # Intialize the plan
    self.plan = None

    # Getting Basic Information
    self.planning_frame = self.group.get_planning_frame()

    # Set path_to_goal to the FollowTrajectoryClient Class
    self.path_to_goal=FollowTrajectoryClient()

    # Set default trajectory velocity for cartesian path
    self.vel = 0.8

    # Set default acceleration for cartesian path
    self.accel = 0.7

  def waypoint_callback(self,msg):
      self.waypoints = []
      # Append poses to a list
      for i in range(len(msg.poses)):
          self.waypoints.append(msg.poses[i])

  def vel_callback(self,msg):
      self.vel   = msg.data

      self.accel = (self.vel**2) / ( 5 * 0.55  )

  def interface_callback(self,gui_input):

      if gui_input.data == "0":
          self.plan = self.plan_cartesian_path(self.waypoints)

      elif gui_input.data == "1":
          self.execute_plan(self.plan)

      elif gui_input.data == "2":
          self.path_to_goal.init_pose()

      elif gui_input.data == "3":
          self.path_to_goal.tuck_pose()

  def plan_cartesian_path(self, waypoints):

    ## Cartesian Paths
    (plan, fraction) = self.group.compute_cartesian_path(
                                       waypoints,   # waypoints to follow
                                       0.1,              # eef_step
                                       0.00)             # jump_threshold

    # plan = self.group.retime_trajectory(self.robot.get_current_state(),plan,.57)
    plan = self.group.retime_trajectory(self.robot.get_current_state(),
                                        plan,
                                        velocity_scaling_factor = self.vel,
                                        acceleration_scaling_factor = self.accel)

    t = plan.joint_trajectory.points[-1].time_from_start
    seconds = t.to_sec()
    self.duration_pub.publish(seconds)

    # Note: We are just planning, not asking move_group to actually move the robot yet:
    return plan

  def execute_plan(self, plan):
 #     print ("WAYPOINTS ARE:", len(self.waypoints), self.waypoints)
      self.group.execute(plan, wait=True)


class FollowTrajectoryClient(object):

    def __init__(self):
        rospy.loginfo("Waiting for MoveIt...")
        self.client = MoveGroupInterface("arm_with_torso", "base_link")
        rospy.loginfo("...connected")
        self.scene = PlanningSceneInterface("base_link")
        self.scene.addBox("keepout", 0.2, 0.5, 0.05, 0.15, 0.0, 0.375)

    def tuck_pose(self, vel = .4):

        # Padding does not work (especially for self collisions)
        # So we are adding a box above the base of the robot
        joints = ["torso_lift_joint", "shoulder_pan_joint", "shoulder_lift_joint", "upperarm_roll_joint",
                  "elbow_flex_joint", "forearm_roll_joint", "wrist_flex_joint", "wrist_roll_joint"]
        pose = [0.05, 1.32, 1.40, -0.2, 1.72, 0.0, 1.66, 0.0]
        while not rospy.is_shutdown():
            result = self.client.moveToJointPosition(joints,
                                                     pose,
                                                     tolerance = 0.02,
                                                     max_velocity_scaling_factor=vel)
            if result and result.error_code.val == MoveItErrorCodes.SUCCESS:
                self.scene.removeCollisionObject("keepout")
                rospy.loginfo("done")
                return

    def init_pose(self, vel = .4):

        # Padding does not work (especially for self collisions)
        # So we are adding a box above the base of the robot
        scene = PlanningSceneInterface("base_link")

        scene.addBox("keepout", 0.2, 0.5, 0.05, 0.15, 0.0, 0.375)

        joints = ["torso_lift_joint", "shoulder_pan_joint", "shoulder_lift_joint", "upperarm_roll_joint",
                  "elbow_flex_joint", "forearm_roll_joint", "wrist_flex_joint", "wrist_roll_joint"]
        pose = [.05, 1.41, 0.30, -0.22, -2.25, -1.56, 1.80, -0.37,]
        while not rospy.is_shutdown():
            result = self.client.moveToJointPosition(joints,
                                                     pose,
                                                     tolerance = 0.02,
                                                     max_velocity_scaling_factor=vel)
            if result and result.error_code.val == MoveItErrorCodes.SUCCESS:
                scene.removeCollisionObject("keepout")
                rospy.loginfo("done")
                return


if __name__=="__main__":
    rospy.init_node('execute_path',anonymous=True)
    ExecutePath()
    rospy.spin()
