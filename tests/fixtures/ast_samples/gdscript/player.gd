class_name Player
extends CharacterBody2D

var speed := 200.0
var health := 100

func _physics_process(delta: float) -> void:
    var velocity := Input.get_vector("left", "right", "up", "down")
    move_and_slide()

func take_damage(amount: int) -> void:
    health -= amount
    if health <= 0:
        queue_free()
