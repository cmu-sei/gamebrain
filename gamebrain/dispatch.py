# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

import asyncio
import json
import logging
import traceback

from dataclasses import dataclass
from pydantic import ValidationError

from gamebrain import db
from .gamedata.cache import (
    TeamID,
    GameStateManager,
    GamespaceStateOutput,
)
from .clients.topomojo import create_dispatch, poll_dispatch


class GamespaceStatusTask:
    settings: "SettingsModel"

    challenge_tasks_config: list["ChallengeTask"]

    @classmethod
    async def init(cls, settings: "SettingsModel"):
        cls.settings = settings
        cls.challenge_tasks_config = cls.settings.game.challenge_tasks

        logging.info("GamespaceStatusTask.init called.")

        return await cls._grader_task()

    @dataclass
    class TeamDispatches:
        challenge_tasks: dict["ChallengeTask", dict]
        grading: dict

    # Mutable assignment is okay, since all the methods are class methods.
    _existing_dispatches: dict[TeamID, TeamDispatches] = {}

    @classmethod
    async def _submit_grading_dispatch(cls, gamespace_id):
        return await create_dispatch(
            gamespace_id,
            cls.settings.game.grading_vm_name,
            cls.settings.game.grading_vm_dispatch_command,
        )

    @classmethod
    async def _submit_challenge_task_dispatch(
        cls, gamespace_id, task_vm_name: str, task_file_path: str
    ):
        return await create_dispatch(
            gamespace_id,
            task_vm_name,
            task_file_path,
        )

    @classmethod
    def _log_dispatch_status(cls, dispatch_status: dict) -> str | None:
        result, error = dispatch_status.get("result"), dispatch_status.get("error")
        if not (result or error):
            # Dispatch hasn't finished yet.
            return
        if error:
            # logging.error(f"Dispatch had an error: {error}")
            return
        logging.info(f"Dispatch completed successfully: {result}")
        return result

    @classmethod
    async def _handle_grading_dispatch(
        cls, grading_dispatch_dict: dict, team_id: TeamID, gamespace_id: str
    ):
        """
        Modifies grading_dispatch_dict in-place.
        """
        dispatch_id = grading_dispatch_dict.get("id")
        if not dispatch_id:
            grading_dispatch_dict.update(
                await cls._submit_grading_dispatch(gamespace_id)
            )
            logging.info(f"Sent grading dispatch for team {team_id}.")
            return
        grading_dispatch_dict.clear()
        status = await poll_dispatch(dispatch_id)

        result = cls._log_dispatch_status(status)
        if not result:
            return

        try:
            grading_result = GamespaceStateOutput(**json.loads(result))
        except (
            json.decoder.JSONDecodeError,
            ValidationError,
        ) as e:
            logging.error(
                f"Unable to parse JSON state data from challenge server dispatch: {result}\n",
                f"{str(e)}",
            )
            return
        except Exception as e:
            logging.exception(
                f"Got an unknown exception from trying to validate grading result: {str(e)}"
            )
            return

        if not grading_result:
            return
        # Better to use the formatted result than the raw string from the challenge, to make the logs easier to read.
        formatted_result = json.dumps(grading_result.dict(), indent=2)
        logging.info(
            f"Got a grading result from team {team_id}'s challenge:\n{formatted_result}"
        )
        await GameStateManager.dispatch_grading_task_update(team_id, grading_result)

    @classmethod
    async def _handle_challenge_task_dispatch(
        cls,
        challenge_task_dispatch_dict: dict,
        team_id: TeamID,
        gamespace_id: str,
        challenge_task: "ChallengeTask",
    ):
        """
        Modifies challenge_task_dispatch_dict in-place.
        """
        dispatch_id = challenge_task_dispatch_dict.get("id")
        if not dispatch_id:
            challenge_task_dispatch_dict.update(
                await cls._submit_challenge_task_dispatch(
                    gamespace_id,
                    challenge_task.vm_name,
                    challenge_task.dispatch_command,
                )
            )
            logging.info(
                f"Sent grading dispatch for team {team_id} and task {challenge_task.task_id}."
            )
            return

        challenge_task_dispatch_dict.clear()
        status = await poll_dispatch(dispatch_id)
        result = cls._log_dispatch_status(status)

        # Technically, the file is JSON-formatted with a key: value pair, but I only need the value.
        if result and "success" in result.lower():
            logging.info(f"Got a challenge task success from {team_id}:\n{result}")
            await GameStateManager.dispatch_challenge_task_complete(
                team_id, challenge_task.task_id
            )
        elif result and "fail" in result.lower():
            logging.info(f"Got a challenge task fail from {team_id}:\n{result}")
            await GameStateManager.dispatch_challenge_task_failed(
                team_id, challenge_task.task_id
            )
        else:
            logging.debug(f"Dispatch completed, without result: \n{result}")

    @classmethod
    async def _grader_task(cls):
        while True:
            try:
                await asyncio.sleep(30)

                teams = await db.get_teams_with_gamespace_ids()
                logging.info(
                    f"Dispatch cycle is running. The current teams are active: {json.dumps(teams, indent=2)}"
                )

                for team_id, gamespace_id in teams.items():

                    team_dispatches = cls._existing_dispatches.get(
                        team_id,
                        cls.TeamDispatches(
                            grading={},
                            challenge_tasks={
                                task: {} for task in cls.challenge_tasks_config
                            },
                        ),
                    )

                    await cls._handle_grading_dispatch(
                        team_dispatches.grading, team_id, gamespace_id
                    )
                    for task, task_dispatch in team_dispatches.challenge_tasks.items():
                        await cls._handle_challenge_task_dispatch(
                            task_dispatch, team_id, gamespace_id, task
                        )

                    cls._existing_dispatches[team_id] = team_dispatches
            except Exception as e:
                logging.exception(f"Dispatch exception: {str(e)}")
