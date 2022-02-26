import re

import nextcord
import lavalink
from nextcord.ext import commands

url_rx = re.compile(r'https?://(?:www\.)?.+')

class LavalinkVoiceClient(nextcord.VoiceClient):

    def __init__(self, client: nextcord.Client, channel: nextcord.abc.Connectable):
        self.client = client
        self.channel = channel
        # ensure there exists a client already
        if hasattr(self.client, 'lavalink'):
            self.lavalink = self.client.lavalink
        else:
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(
                    'localhost',
                    2333,
                    'youshallnotpass',
                    'apac',
                    'default-node')
            self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
                't': 'VOICE_SERVER_UPDATE',
                'd': data
                }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
                't': 'VOICE_STATE_UPDATE',
                'd': data
                }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_deaf=True)

    async def disconnect(self, *, force: bool) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that
        # would set channel_id to None doesn't get dispatched after the 
        # disconnect
        player.channel_id = None
        self.cleanup()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        

        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(bot.user.id)
            bot.lavalink.add_node('127.0.0.1', 2333, 'youshallnotpass', 'apac', 'default-node')  # Host, Port, Password, Region, Name

        lavalink.add_event_hook(self.track_hook)

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()

    async def cog_before_invoke(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author share a mutual voicechannel.

        return guild_check

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original)
            # The above handles errors thrown in this cog and shows them to the user.
            # This shouldn't be a problem as the only errors thrown in this cog are from `ensure_voice`
            # which contain a reason string, such as "Join a voicechannel" etc. You can modify the above
            # if you want to do things differently.

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        # Create returns a player if one exists, otherwise creates.
        # This line is important because it ensures that a player always exists for a guild.

        # Most people might consider this a waste of resources for guilds that aren't playing, but this is
        # the easiest and simplest way of ensuring players are created.

        # These are commands that require the bot to join a voicechannel (i.e. initiating playback).
        # Commands such as volume/skip etc don't require the bot to be in a voicechannel so don't need listing here.
        should_connect = ctx.command.name in ('play',)

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Our cog_command_error handler catches this and sends it to the voicechannel.
            # Exceptions allow us to "short-circuit" command invocation via checks so the
            # execution state of the command goes no further.
            raise commands.CommandInvokeError('Join a voicechannel first.')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Not connected.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            # await guild.voice_client.disconnect(force=True)

        if isinstance(event, lavalink.events.TrackEndEvent):
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)

            if(player.fetch('loopType') == 1):
                await player.play(player.fetch('loopMusic'))

        elif isinstance(event, lavalink.events.TrackStartEvent):
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            player = self.bot.lavalink.player_manager.get(guild_id)
            

            NowPlay = nextcord.Embed(title="กำลังเล่นเพลง :", description=f"[{player.current.title}]({player.current.uri})")
            NowPlay.set_image(url=f"https://i3.ytimg.com/vi/{player.current.uri[-11:]}/maxresdefault.jpg")


            class PlayerButton(nextcord.ui.View):
                
                # PAUSE
                @nextcord.ui.button(label="หยุด", style=nextcord.ButtonStyle.primary, emoji="⏸️", row=0)
                async def pause_callback(self, button, interaction): 
                    if(player.paused):
                        button.label="หยุด"
                        button.emoji="⏸️"
                        await player.set_pause(False)
                    else:
                        button.label="เล่น"
                        button.emoji="▶️"
                        await player.set_pause(True)
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send("หยุดเล่นเพลง", delete_after=15)

                # SKIP
                @nextcord.ui.button(label="ข้าม", style=nextcord.ButtonStyle.primary, emoji="⏭️", row=0)
                async def skip_callback(self, button, interaction): 
                    await player.skip()
                    await interaction.response.send_message("ข้ามไปเพลงต่อไป", delete_after=15)

                # LOOP
                @nextcord.ui.button(label="ลูป", style=nextcord.ButtonStyle.primary, emoji="🔁", row=0)
                async def loop_callback(self, button, interaction):
                    if(player.fetch('loopType') is None): # Loop one
                        player.set_repeat(False)
                        player.store('loopMusic', player.current)
                        player.store('loopType', 1)
                        await interaction.response.send_message("เล่นวนเพลงเดียว", delete_after=15)

                    elif(player.fetch('loopType') < 2): #Loop queue
                        player.set_repeat(True)
                        player.delete('loopMusic')
                        player.store('loopType', player.fetch('loopType')+1)
                        await interaction.response.send_message("เล่นวนทั้งลิสต์", delete_after=15)

                    else:
                        player.set_repeat(False)
                        player.delete('loopType') #Loop off
                        await interaction.response.send_message("ยกเลิกการเล่นวน", delete_after=15)

                    print(player.fetch('loopType'))
                    print(player.current)

                @nextcord.ui.button(label="ออก", style=nextcord.ButtonStyle.danger, emoji="⏏️", row=0)
                async def leave_callback(self, button, interaction): # LEAVE
                    if not player.is_connected:
                        return await interaction.send('ฉันยังไม่ได้เล่นเพลงเลยนะ !!!')
                    if not interaction.user.voice or (player.is_connected and interaction.user.voice.channel.id != int(player.channel_id)):
                        return await interaction.send('คุณไม่ได้อยู่ในห้องของเรานะ !!!')
                    player.queue.clear()
                    await player.stop()
                    await guild.voice_client.disconnect(force=True)
                    await interaction.response.send_message("ไปก่อนนะ จุ๊บๆ", delete_after=15)

                @nextcord.ui.button(label="ลดเสียง", style=nextcord.ButtonStyle.red, emoji="🔉" , row=1)
                async def reduceVol_callback(self, button, interaction):
                    await player.set_volume(player.volume - 20)
                    await interaction.response.send_message(f"ลดเสียงเหลือ: {player.volume}", delete_after=15)

                @nextcord.ui.button(label="เพื่มเสียง", style=nextcord.ButtonStyle.green, emoji="🔊", row=1)
                async def increaseVol_callback(self, button, interaction):
                    await player.set_volume(player.volume + 20)
                    await interaction.response.send_message(f"เพิ่มเสียงเป็น: {player.volume}", delete_after=15)

                @nextcord.ui.button(label="ล้างคิวเพลง", style=nextcord.ButtonStyle.primary, emoji="⚙️", row=1)
                async def clearQueue_List(self, button, interaction):
                    await player.queue.clear()
                    await interaction.response.send_message("เคลียร์คิวเพลง", delete_after=15)

            ButtonMenu = PlayerButton()

            chanel = self.bot.get_channel(934496557900914759)
            await chanel.send(embed=NowPlay, view=ButtonMenu)
            
        

    # Command
    @commands.command(aliases=['p','เล่นเพลง'])
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        query = query.strip('<>')

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Nothing found!')

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']

            for track in tracks:
                # Add all of the tracks from the playlist to the queue.
                player.add(requester=ctx.author.id, track=track)
        else:
            track = results['tracks'][0]

            # You can attach additional information to audiotracks through kwargs, however this involves
            # constructing the AudioTrack class yourself.
            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(requester=ctx.author.id, track=track)

        # the current track.
        if not player.is_playing:
            await player.play()


    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        queue_embed = nextcord.Embed(colour=0x98EBF1, title="NOW PLAYING", description=f"[{player.current.title}]({player.current.uri}) {lavalink.format_time(player.current.duration)}")
        queue_lists = ""

        if len(player.queue) != 0:
            for x in range(0, len(player.queue)):
                queue_lists += f"{str(x+1)}. [{player.queue[x].title}]({player.queue[x].uri}) {lavalink.format_time(player.queue[x].duration)}\n"
        else:
            queue_lists = "There isn\'t any songs in queue"

        queue_embed.add_field(name=f"Queue {len(player.queue)} song(s)", value=f"{queue_lists}", inline=False)
        await ctx.send(embed=queue_embed, delete_after=20)

    @commands.command(name='remove')
    async def remove(self, ctx, par: int = None):

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if par is None:
            return await ctx.send('Please insert number of music in queue!')
        else:
            player.queue.pop(par-1)
            return await ctx.send(f"Remove {player.queue[par].title}")

    @commands.command(name='clear')
    async def clear(self, ctx):
        player =  self.bot.lavalink.player_manger.get(ctx.guild.id)
        player.queue.clear()
        await ctx.send("Queue has been cleared")

def setup(bot):
    bot.add_cog(Music(bot))