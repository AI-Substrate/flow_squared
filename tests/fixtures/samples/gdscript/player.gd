## Player character controller.
## Handles movement, health, and damage using CharacterBody2D physics.
class_name Player
extends CharacterBody2D

## Movement speed in pixels per second.
var speed := 200.0
## Current health points.
var health := 100

## Process physics movement each frame.
## Uses input vector for 4-directional movement.
func _physics_process(delta: float) -> void:
    var velocity := Input.get_vector("left", "right", "up", "down")
    move_and_slide()

## Apply damage to the player.
## Removes player from scene if health reaches zero.
## @param amount - Damage points to subtract from health.
func take_damage(amount: int) -> void:
    health -= amount
    if health <= 0:
        queue_free()
