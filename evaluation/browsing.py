from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Dict, List, Union
import re
import base64
import os

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import BrowseInteractiveAction
from openhands.events.observation import BrowserOutputObservation
from openhands.runtime.base import Runtime


def _decode_screenshot_to_bytes(screenshot: str) -> bytes:
    """Decode a screenshot string to bytes robustly.

    Handles optional data URL prefixes and missing base64 padding.
    Returns empty bytes on failure.
    """
    if not screenshot:
        return b""
    try:
        content = screenshot
        if content.startswith('data:image/'):
            # Strip data URL header like: data:image/png;base64,
            header_end = content.find(',')
            content = content[header_end + 1:] if header_end != -1 else content
        # Fix missing padding
        padding = len(content) % 4
        if padding:
            content = content + ('=' * (4 - padding))
        return base64.b64decode(content, validate=False)
    except Exception:
        logger.warning("Failed to decode screenshot; skipping save.")
        return b""


class ActionType(Enum):
    GOTO = auto()
    FILL = auto()
    CLICK = auto()
    NOOP = auto()


@dataclass
class Selector:
    """
    Represents either a direct anchor ID or a descriptive selector
    """
    value: str
    is_anchor: bool = False
    
    def __str__(self) -> str:
        return f"{self.value}"

@dataclass
class BrowserAction:
    """Base class for all browser actions"""
    action_type: ActionType
    
    def to_instruction(self) -> str:
        """Convert the action to a browser instruction string"""
        raise NotImplementedError

@dataclass
class GotoAction(BrowserAction):
    url: str
    
    def __init__(self, url: str):
        super().__init__(ActionType.GOTO)
        self.url = url
    
    def to_instruction(self) -> str:
        return f'goto("{self.url}")'


@dataclass
class NoopAction(BrowserAction):
    milliseconds: int
    
    def __init__(self, milliseconds: int):
        super().__init__(ActionType.NOOP)
        self.milliseconds = milliseconds
    
    def to_instruction(self) -> str:
        return f'noop({self.milliseconds})'


@dataclass
class InputAction(BrowserAction):
    selector: Selector
    value: str
    
    def __init__(self, selector: Union[str, Selector], value: str):
        super().__init__(ActionType.FILL)
        self.selector = selector if isinstance(selector, Selector) else Selector(selector)
        self.value = value
    
    def to_instruction(self) -> str:
        return f'fill("{self.selector}", "{self.value}")'

@dataclass
class ClickAction(BrowserAction):
    selector: Selector
    
    def __init__(self, selector: Union[str, Selector]):
        super().__init__(ActionType.CLICK)
        self.selector = selector if isinstance(selector, Selector) else Selector(selector)
    
    def to_instruction(self) -> str:
        return f'click("{self.selector}")'

def parse_content_to_elements(content: str) -> Dict[str, str]:
    """Parse the observation content into a dictionary mapping anchors to their descriptions"""
    elements = {}
    current_anchor = None
    description_lines = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check for anchor line
        anchor_match = re.match(r'\[(\d+)\](.*)', line)
        if anchor_match:
            # Save previous element if it exists
            if current_anchor and description_lines:
                elements[current_anchor] = ' '.join(description_lines)
            
            # Start new element
            current_anchor = anchor_match.group(1)
            description_lines = [anchor_match.group(2).strip()]
        else:
            # Add to current description if we have an anchor
            if current_anchor:
                description_lines.append(line)
    
    # Save last element
    if current_anchor and description_lines:
        elements[current_anchor] = ' '.join(description_lines)
        
    return elements

def find_matching_anchor(content: str, selector: str) -> Optional[str]:
    """Find the anchor ID that matches the given selector description"""
    elements = parse_content_to_elements(content)
    
    # Clean up selector and create a pattern
    selector = selector.lower().strip()
    
    for anchor, description in elements.items():
        description = description.lower().strip()
        if selector in description:
            return anchor

    return None

def resolve_action(action: BrowserAction, content: str) -> BrowserAction:
    """
    Resolve any descriptive selectors in the action to anchor IDs based on the content.
    With fallback heuristics when exact match is not found.
    Returns a new action with resolved selectors.
    """
    if isinstance(action, (InputAction, ClickAction)):
        if not action.selector.is_anchor:
            anchor = find_matching_anchor(content, action.selector.value)
            if anchor:
                new_selector = Selector(anchor, is_anchor=True)
                if isinstance(action, InputAction):
                    return InputAction(new_selector, action.value)
                else:
                    return ClickAction(new_selector)
            else:
                # Fallback: try to find a reasonable element
                elements = parse_content_to_elements(content)
                lowered_items = [(a, d.lower()) for a, d in elements.items()]

                if isinstance(action, InputAction):
                    # Look for textbox elements
                    textbox_candidates = [(a, d) for a, d in lowered_items if 'textbox' in d]
                    if textbox_candidates:
                        # Prefer focused, then clickable, then any
                        focused = [a for a, d in textbox_candidates if 'focused' in d]
                        if focused:
                            logger.warning(f"Using focused textbox fallback for {action.selector}")
                            return InputAction(Selector(focused[0], is_anchor=True), action.value)
                        clickable = [a for a, d in textbox_candidates if 'clickable' in d]
                        if clickable:
                            logger.warning(f"Using clickable textbox fallback for {action.selector}")
                            return InputAction(Selector(clickable[0], is_anchor=True), action.value)
                        logger.warning(f"Using first textbox fallback for {action.selector}")
                        return InputAction(Selector(textbox_candidates[0][0], is_anchor=True), action.value)
                else:  # ClickAction
                    # Look for button/clickable elements
                    button_candidates = [(a, d) for a, d in lowered_items if 'button' in d or 'clickable' in d]
                    if button_candidates:
                        # Prefer login-related buttons
                        login_related = [a for a, d in button_candidates if 'login' in d or 'sign' in d]
                        if login_related:
                            logger.warning(f"Using login-related button fallback for {action.selector}")
                            return ClickAction(Selector(login_related[0], is_anchor=True))
                        logger.warning(f"Using first button fallback for {action.selector}")
                        return ClickAction(Selector(button_candidates[0][0], is_anchor=True))

                logger.error(f"NO MATCH FOUND FOR SELECTOR, {action.selector}")
                logger.error(f"Page content (first 500 chars): {content[:500]}")
                logger.error(f"Available elements: {list(elements.keys())}")
                return None
    return action


def pre_login(runtime: Runtime, services: List[str], save_screenshots=True, screenshots_dir='screenshots'):
    """
    Logs in to all the websites that are needed for the evaluation.
    Once logged in, the sessions would be cached in the browser, so OpenHands
    agent doesn't need to log in to these websites again.
    """
    owncloud_login_actions = [
        GotoAction("http://127.0.0.1:8092"),
        NoopAction(1000),
        InputAction(
            "textbox '', clickable, focused, required",
            "theagentcompany"
        ),
        NoopAction(1000),
        InputAction(
            "textbox '', clickable, required",
            "theagentcompany"
        ),
        NoopAction(1000),
        ClickAction("button '', clickable"),
        NoopAction(1000)
    ]

    rocketchat_login_actions = [
        # 1) 直达登录页（使用 3002）
        GotoAction("http://127.0.0.1:3002/login"),
        NoopAction(1000),
        InputAction(
            "textbox '', clickable, focused",
            "theagentcompany"
        ),
        NoopAction(1000),
        InputAction(
            "textbox '', clickable",
            "theagentcompany"
        ),
        NoopAction(1000),
        ClickAction("button 'Login', clickable")
    ]

    gitlab_login_actions = [
        GotoAction("http://127.0.0.1:8929/users/sign_in"),
        NoopAction(1000),
        InputAction(
            "textbox 'Username or primary email'",
            "root"
        ),
        NoopAction(1000),
        InputAction(
            "textbox 'Password'",
            "theagentcompany"
        ),
        NoopAction(1000),
        ClickAction("button 'Sign in', clickable")
    ]

    # devnote: plane reset is not stable, and sometimes it fails to launch
    # in which case the login action will fail, and then we would skip the task
    plane_login_actions = [
        GotoAction("http://127.0.0.1:8091"),
        NoopAction(1000),
        InputAction(
            "textbox 'Email', clickable, focused",
            "agent@company.com",
        ),
        NoopAction(1000),
        ClickAction("button 'Continue'"),
        NoopAction(1000),
        InputAction(
            "textbox 'Enter password', clickable",
            "theagentcompany"
        ),
        NoopAction(1000),
        ClickAction("button 'Go to workspace'")
    ]

    all_login_actions = [
        ('owncloud', owncloud_login_actions),
        ('rocketchat', rocketchat_login_actions),
        ('gitlab', gitlab_login_actions),
        ('plane', plane_login_actions),
    ]
    
    for (website_name, login_actions) in all_login_actions:
        if website_name not in services:
            logger.info(f"Skipping login for {website_name} because it's not in the list of services to reset")
            continue

        if save_screenshots:
            directory = os.path.join(screenshots_dir, website_name)
            if not os.path.exists(directory):
                os.makedirs(directory)
            image_id = 0
        logged_in = False
        obs: BrowserOutputObservation = None
        for action_idx, action in enumerate(login_actions):
            # Resolve any descriptive selectors to anchor IDs
            if obs:
                # Rocket.Chat 专项：在每次动作前检查状态
                if website_name == 'rocketchat':
                    content_text = obs.get_agent_obs_text() if hasattr(obs, 'get_agent_obs_text') else ''
                    content_lc = content_text.lower() if content_text else ''

                    # 2) 若出现 Site URL 弹窗，点击 Yes
                    if ('site url is configured' in content_lc and 'do you want to change' in content_lc):
                        try:
                            yes_action = ClickAction("button 'Yes', clickable")
                            yes_action = resolve_action(yes_action, content_text) or yes_action
                            yes_instr = yes_action.to_instruction()
                            yes_browser_action = BrowseInteractiveAction(browser_actions=yes_instr)
                            yes_browser_action.set_hard_timeout(10000)
                            logger.info(yes_browser_action, extra={'msg_type': 'ACTION'})
                            obs = runtime.run_action(yes_browser_action)
                            logger.debug(obs, extra={'msg_type': 'OBSERVATION'})
                            content_text = obs.get_agent_obs_text() if hasattr(obs, 'get_agent_obs_text') else content_text
                            content_lc = content_text.lower() if content_text else content_lc
                        except Exception:
                            logger.warning("Failed to click 'Yes' on Site URL prompt; continue.")

                    # 3) 若已登录（侧边栏/Home 等关键字），则跳过后续输入
                    if (('omnichannel' in content_lc or 'home' in content_lc) and 'login' not in content_lc):
                        logger.info("Rocket.Chat appears logged-in; skipping further login steps.")
                        logged_in = True
                        break

                action = resolve_action(action, obs.get_agent_obs_text())

            if not action:
                logger.error(f"FAILED TO RESOLVE ACTION, {action}")
                raise Exception(f"FAILED TO RESOLVE ACTION, maybe the service is not available")

            # Convert the action to an instruction string
            instruction = action.to_instruction()
            
            browser_action = BrowseInteractiveAction(
                browser_actions=instruction
            )
            browser_action.set_hard_timeout(10000)
            logger.info(browser_action, extra={'msg_type': 'ACTION'})
            obs: BrowserOutputObservation = runtime.run_action(browser_action)
            logger.debug(obs, extra={'msg_type': 'OBSERVATION'})
            if save_screenshots:
                screenshot_str = getattr(obs, 'screenshot', '')
                if screenshot_str:
                    logger.debug(f"Screenshot string length: {len(screenshot_str)}")
                image_data = _decode_screenshot_to_bytes(screenshot_str)
                if image_data:
                    filepath = os.path.join(directory, f'{image_id}.png')
                    with open(filepath, 'wb') as file:
                        file.write(image_data)
                    logger.debug(f"Saved screenshot {filepath}, size: {len(image_data)} bytes")
                    image_id += 1
                else:
                    logger.warning(f"Failed to decode screenshot for action {action_idx}")