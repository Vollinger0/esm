# text output format

### this happened when i connected
Event: Event_Player_Connected, Seq: 0, Data: {"id":2142}

### ok, this is a player's private info
Event: Event_PdaStateChange, Seq: 0, Data: {"Name":"pda_iG40h","StateChange":1,"PlayerId":2142}

### this might be funny to use, e.g. when somebody goes into godmode, someone could comment on that
Event: Event_ConsoleCommand, Seq: 0, Data: {"command":"gm ic","allowed":true,"playerEntityId":2142}

### global chat event, notice there are 2 events here
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"hello there","recipientEntityId":-1,"recipientFactionId":0,"type":3}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":0,"SenderEntityId":2142,"SenderFaction":{"Group":1,"Id":2142},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":0},"Text":"hello there","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

### global chat again
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"hello from the global chat","recipientEntityId":-1,"recipientFactionId":0,"type":3}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":0,"SenderEntityId":2142,"SenderFaction":{"Group":1,"Id":2142},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":0},"Text":"hello from the global chat","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

### private chat 
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"ello to myself in private","recipientEntityId":2142,"recipientFactionId":0,"type":8}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":3,"SenderEntityId":2142,"SenderFaction":{"Group":1,"Id":2142},"SenderNameOverride":null,"RecipientEntityId":2142,"RecipientFaction":{"Group":0,"Id":0},"Text":"ello to myself in private","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

### server tab
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"ello to the server tab","recipientEntityId":-1,"recipientFactionId":0,"type":9}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":4,"SenderEntityId":2142,"SenderFaction":{"Group":1,"Id":2142},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":0},"Text":"ello to the server tab","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

### faction chat 
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"hello to faction chat","recipientEntityId":-1,"recipientFactionId":100,"type":5}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":1,"SenderEntityId":2142,"SenderFaction":{"Group":0,"Id":100},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":100},"Text":"hello to faction chat","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

### alliance chat
Event: Event_ChatMessage, Seq: 201, Data: {"playerId":2142,"msg":"hello to alliance chat","recipientEntityId":-1,"recipientFactionId":0,"type":5}
Event: 201, Seq: 201, Data: {"GameTime":0,"SenderType":1,"Channel":2,"SenderEntityId":2142,"SenderFaction":{"Group":0,"Id":100},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":0},"Text":"hello to alliance chat","IsTextLocaKey":false,"Arg1":null,"Arg2":null}

## json output format

### global chat
{"CmdId":"Event_ChatMessage","SeqNum":201,"Data":{"playerId":2142,"msg":"ello from glogal chat again","recipientEntityId":-1,"recipientFactionId":0,"type":3}}
{"CmdId":201,"SeqNum":201,"Data":{"GameTime":0,"SenderType":1,"Channel":0,"SenderEntityId":2142,"SenderFaction":{"Group":0,"Id":100},"SenderNameOverride":null,"RecipientEntityId":-1,"RecipientFaction":{"Group":0,"Id":0},"Text":"ello from glogal chat again","IsTextLocaKey":false,"Arg1":null,"Arg2":null}}

### again, private player info
{"CmdId":"Event_PdaStateChange","SeqNum":0,"Data":{"Name":"pda_iG40h","StateChange":2,"PlayerId":2142}}

### player disconnected 
{"CmdId":"Event_Player_Disconnected","SeqNum":0,"Data":{"id":2142}}

### playfield disconnected
{"CmdId":"Event_Playfield_Unloaded","SeqNum":0,"Data":{"sec":0.2,"playfield":"Haven","processId":3152}}
