import glob
import os
import json

BedrockLevels = []
JavaVanillaLevels = []
JavaForgeLevels = []


def find_levels():
    this_dir = os.path.dirname(__file__)
    for path in glob.glob(
        os.path.join(
            this_dir,
            "**",
            "world_test_data.json"
        ),
        recursive=True
    ):
        rel_path = os.path.dirname(os.path.relpath(path, this_dir))
        with open(path) as f:
            test_data = json.load(f)
        platform = test_data["world_data"]["platform"]
        if platform == "java":
            origin = test_data["world_data"]["origin"]
            if origin == "vanilla":
                JavaVanillaLevels.append(rel_path)
            elif origin == "forge":
                JavaForgeLevels.append(rel_path)
            else:
                raise Exception(f"Unknown origin {origin}")
        elif platform == "bedrock":
            BedrockLevels.append(rel_path)
        else:
            raise Exception(f"Unknown platform {platform}")


find_levels()
del find_levels

JavaLevels = [*JavaVanillaLevels, *JavaForgeLevels]

levels = [
    *BedrockLevels,
    *JavaLevels,
]
