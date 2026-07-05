from __future__ import annotations

from .channel_groups import ChannelGroupMixin
from .channel_mutations import ChannelMutationMixin
from .channel_presenters import ChannelPresenterMixin
from .channel_read import ChannelReadMixin
from .channel_sync import ChannelSyncMixin


class ChannelRepositoryMixin(
    ChannelReadMixin,
    ChannelPresenterMixin,
    ChannelGroupMixin,
    ChannelMutationMixin,
    ChannelSyncMixin,
):
    """Combines channel reads, presentation, mutation, groups, and key sync behavior."""
