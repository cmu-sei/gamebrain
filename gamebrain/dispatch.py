import asyncio
import json
import logging

from dataclasses import dataclass
from pydantic import ValidationError

from gamebrain import db
from .gamedata.cache import (
    TeamID,
    GameStateManager,
    GamespaceStateOutput,
    RedRaiderOutput,
)
from .clients.topomojo import create_dispatch, poll_dispatch


class GamespaceStatusTask:
    dispatcher_task = None

    settings: "SettingsModel"

    @classmethod
    async def init(cls, settings: "SettingsModel"):
        cls.settings = settings

        return await cls._grader_task()

    @dataclass
    class TeamDispatches:
        red_raider: dict
        grading: dict

    # Mutable assignment is okay, since all the methods are class methods.
    _existing_dispatches: dict[TeamID, TeamDispatches] = {}

    @classmethod
    async def _submit_grading_dispatch(cls, gamespace_id):
        return await create_dispatch(
            gamespace_id,
            cls.settings.game.grading_vm_name,
            cls.settings.game.grading_vm_file_path,
        )

    @classmethod
    async def _submit_red_raider_dispatch(cls, gamespace_id):
        return await create_dispatch(
            gamespace_id,
            cls.settings.game.red_raider_vm_name,
            cls.settings.game.red_raider_file_path,
        )

    @classmethod
    async def _grader_task(cls):
        while True:
            await asyncio.sleep(30)

            teams = await db.get_teams()

            for team in teams:
                team_id = team.get("id")
                gamespace_id = team.get("gamespace_id")

                team_dispatches = cls._existing_dispatches.get(
                    team_id, cls.TeamDispatches(grading={}, red_raider={})
                )

                dispatch_pair = (team_dispatches.grading, team_dispatches.red_raider)
                for i, dispatch in enumerate(dispatch_pair):
                    id_ = dispatch.get("id")
                    if not id_:
                        match i:
                            case 0:
                                team_dispatches.grading = (
                                    await cls._submit_grading_dispatch(gamespace_id)
                                )
                            case 1:
                                team_dispatches.red_raider = (
                                    await cls._submit_red_raider_dispatch(gamespace_id)
                                )
                    else:
                        status = await poll_dispatch(id_)
                        result, error = status.get("result"), status.get("error")
                        if not (result or error):
                            continue
                        elif result:
                            logging.info(f"Dispatch completed successfully: {result}")
                        elif error:
                            logging.info(f"Dispatch had an error: {error}")
                        match i:
                            case 0:
                                team_dispatches.grading = {}
                                try:
                                    grading_result = GamespaceStateOutput(
                                        **json.loads(result)
                                    )
                                except (
                                    json.decoder.JSONDecodeError,
                                    ValidationError,
                                ) as e:
                                    logging.error(
                                        f"Unable to parse JSON state data from challenge server dispatch: {result}\n",
                                        f"{str(e)}",
                                    )
                                else:
                                    await GameStateManager.team_state_from_gamespace(
                                        team_id, grading_result
                                    )
                            case 1:
                                team_dispatches.red_raider = {}
                cls._existing_dispatches[team_id] = team_dispatches
