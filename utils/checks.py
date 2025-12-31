async def check_subscription(bot, user_id: int) -> bool:
    target_channel = "@highprod"
    try:
        member = await bot.get_chat_member(chat_id=target_channel, user_id=user_id)
        if member.status in ['left', 'kicked', 'banned']:
            return False
        return True
    except Exception as e:
        print(f"Error checking sub: {e}")
        # In case of error (e.g. bot not admin), assume allowed to prevent lock-out? 
        # Or False to enforce?
        # Assuming False to force fixing the bot rights in channel if that's the issue.
        return False 