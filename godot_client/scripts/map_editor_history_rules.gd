extends RefCounted


static func record(undo_stack: Array, redo_stack: Array, snapshot: Dictionary, limit: int) -> void:
	undo_stack.append(snapshot)
	_trim(undo_stack, limit)
	redo_stack.clear()


static func undo(undo_stack: Array, redo_stack: Array, current: Dictionary) -> Dictionary:
	if undo_stack.is_empty():
		return {}
	redo_stack.append(current)
	return undo_stack.pop_back()


static func redo(undo_stack: Array, redo_stack: Array, current: Dictionary, limit: int) -> Dictionary:
	if redo_stack.is_empty():
		return {}
	undo_stack.append(current)
	_trim(undo_stack, limit)
	return redo_stack.pop_back()


static func _trim(stack: Array, limit: int) -> void:
	while stack.size() > limit:
		stack.pop_front()
