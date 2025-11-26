-- PetWeaverEnemyRecorder.lua
-- Records enemy pet abilities during battles for AI script generation

local addonName, addon = ...

PetWeaverEnemyRecorder = {}
local recorder = PetWeaverEnemyRecorder

-- Saved variables
PetWeaverEnemyRecordings = PetWeaverEnemyRecordings or {}

-- Current battle state
local currentBattle = nil
local currentTurn = 0
local isRecording = false

function recorder:Initialize()
    print("|cFF00FF00PetWeaver Enemy Recorder loaded!|r Type /pwrecord to toggle recording")
    
    -- Slash command
    SLASH_PWRECORD1 = "/pwrecord"
    SlashCmdList["PWRECORD"] = function(msg)
        self:ToggleRecording()
    end
    
    -- Hook battle events
    self:RegisterEvents()
end

function recorder:RegisterEvents()
    local frame = CreateFrame("Frame")
    frame:RegisterEvent("PET_BATTLE_OPENING_START")
    frame:RegisterEvent("PET_BATTLE_TURN_STARTED")
    frame:RegisterEvent("PET_BATTLE_ACTION_SELECTED")
    frame:RegisterEvent("PET_BATTLE_CLOSE")
    
    frame:SetScript("OnEvent", function(_, event, ...)
        if event == "PET_BATTLE_OPENING_START" then
            self:OnBattleStart()
        elseif event == "PET_BATTLE_TURN_STARTED" then
            self:OnTurnStart()
        elseif event == "PET_BATTLE_ACTION_SELECTED" then
            self:OnActionSelected()
        elseif event == "PET_BATTLE_CLOSE" then
            self:OnBattleEnd()
        end
    end)
end

function recorder:ToggleRecording()
    isRecording = not isRecording
    if isRecording then
        print("|cFF00FF00Enemy recording ENABLED|r - Enemy abilities will be tracked")
    else
        print("|cFFFF0000Enemy recording DISABLED|r")
    end
end

function recorder:OnBattleStart()
    if not isRecording then return end
    
    currentTurn = 0
    
    -- Get enemy info
    local enemyName = C_PetBattles.GetName(Enum.BattlePetOwner.Enemy, 1)
    local battleType = C_PetBattles.IsPlayerNPC(Enum.BattlePetOwner.Enemy) and "NPC" or "PVP"
    
    if battleType ~= "NPC" then
        -- Only record NPC battles
        return
    end
    
    currentBattle = {
        enemyName = enemyName,
        timestamp = time(),
        turns = {},
        enemyPets = {}
    }
    
    -- Record all enemy pets
    for i = 1, C_PetBattles.GetNumPets(Enum.BattlePetOwner.Enemy) do
        local petID = C_PetBattles.GetPetSpeciesID(Enum.BattlePetOwner.Enemy, i)
        local displayID = C_PetBattles.GetDisplayID(Enum.BattlePetOwner.Enemy, i)
        local name = C_PetBattles.GetName(Enum.BattlePetOwner.Enemy, i)
        
        currentBattle.enemyPets[i] = {
            petID = petID,
            displayID = displayID,
            name = name
        }
    end
    
    print("|cFFFFFF00Recording battle vs:|r " .. enemyName)
end

function recorder:OnTurnStart()
    if not currentBattle then return end
    
    currentTurn = currentTurn + 1
    currentBattle.turns[currentTurn] = {
        turnNumber = currentTurn,
        enemyActions = {}
    }
end

function recorder:OnActionSelected()
    if not currentBattle then return end
    
    -- C_Timer to delay so we can capture enemy action after it happens
    C_Timer.After(0.5, function()
        self:RecordEnemyAction()
    end)
end

function recorder:RecordEnemyAction()
    if not currentBattle or not currentBattle.turns[currentTurn] then return end
    
    -- Get active enemy pet
    local activeEnemySlot = C_PetBattles.GetActivePet(Enum.BattlePetOwner.Enemy)
    
    -- Try to get the last ability used by checking combat log
    -- This is tricky - we may need to parse CLEU events
    
    -- For now, record pet states
    local turn = currentBattle.turns[currentTurn]
    
    -- Record enemy pet health/stats after action
    for i = 1, C_PetBattles.GetNumPets(Enum.BattlePetOwner.Enemy) do
        local health = C_PetBattles.GetHealth(Enum.BattlePetOwner.Enemy, i)
        local maxHealth = C_PetBattles.GetMaxHealth(Enum.BattlePetOwner.Enemy, i)
        
        if not turn.enemyActions[i] then
            turn.enemyActions[i] = {}
        end
        
        turn.enemyActions[i].health = health
        turn.enemyActions[i].maxHealth = maxHealth
        turn.enemyActions[i].active = (i == activeEnemySlot)
    end
end

function recorder:OnBattleEnd()
    if not currentBattle then return end
    
    -- Save recording
    local enemyName = currentBattle.enemyName
    
    if not PetWeaverEnemyRecordings[enemyName] then
        PetWeaverEnemyRecordings[enemyName] = {battles = {}}
    end
    
    table.insert(PetWeaverEnemyRecordings[enemyName].battles, currentBattle)
    
    print("|cFF00FF00Recorded battle vs " .. enemyName .. "|r (" .. currentTurn .. " turns)")
    print("Total recordings for this enemy: " .. #PetWeaverEnemyRecordings[enemyName].battles)
    
    currentBattle = nil
end

-- Export function
function recorder:ExportRecordings()
    if not PetWeaverEnemyRecordings or not next(PetWeaverEnemyRecordings) then
        print("|cFFFF0000No recordings to export|r")
        return
    end
    
    print("|cFFFFFF00Recorded Encounters:|r")
    for enemyName, data in pairs(PetWeaverEnemyRecordings) do
        print("  " .. enemyName .. ": " .. #data.battles .. " battles")
    end
    print("Data saved to SavedVariables/PetWeaver.lua")
end

-- Initialize on load
recorder:Initialize()
