class Action:
    id = "base"
    cost = 0
    name = "Base"

    def resolve(
        self,
        battle,
        actor,
        target,
        enemy_action_is_defending=False
    ):
        raise NotImplementedError


class AttackAction(Action):
    id = "attack"
    name = "Удар"

    def resolve(
        self,
        battle,
        actor,
        target,
        enemy_action_is_defending=False
    ):
        damage = battle.calc_damage(
            actor,
            target,
            enemy_action_is_defending
        )

        target.take_damage(damage)

        return {
            "type": "damage",
            "amount": damage
        }


class DefendAction(Action):
    id = "defend"
    name = "Защита"

    def resolve(
        self,
        battle,
        actor,
        target,
        enemy_action_is_defending=False
    ):
        return {
            "type": "defend"
        }


def get_action_by_id(action_id):
    if action_id == "attack":
        return AttackAction()

    if action_id == "defend":
        return DefendAction()

    raise ValueError(f"Неизвестное действие: {action_id}")
