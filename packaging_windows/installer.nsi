; =====================================================================
; SP-Farms Windows Installer Script (NSIS Modern UI 2)
; =====================================================================

!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "SP-Farms"
OutFile "..\dist\installer\SP-Farms-Setup-0.1.0-nsis.exe"
InstallDir "$PROGRAMFILES64\SP-Farms"
InstallDirRegKey HKLM "Software\SP-Farms" "Install_Dir"
RequestExecutionLevel admin

!define MUI_ICON "..\assets\icons\sp_farms.ico"
!define MUI_UNICON "..\assets\icons\sp_farms.ico"
!define MUI_ABORTWARNING

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\SP-Farms.exe"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "SP-Farms (required)" SecCore
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "..\dist\SP-Farms\*.*"

  ; Shortcuts
  CreateDirectory "$SMPROGRAMS\SP-Farms"
  CreateShortcut "$SMPROGRAMS\SP-Farms\SP-Farms.lnk" "$INSTDIR\SP-Farms.exe" "" "$INSTDIR\assets\icons\sp_farms.ico"
  CreateShortcut "$SMPROGRAMS\SP-Farms\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$DESKTOP\SP-Farms.lnk" "$INSTDIR\SP-Farms.exe" "" "$INSTDIR\assets\icons\sp_farms.ico"

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms" "DisplayName" "SP-Farms"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms" "DisplayIcon" "$INSTDIR\assets\icons\sp_farms.ico"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms" "Publisher" "SP-Farms"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms" "DisplayVersion" "0.1.0"
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  ; Remove binary directory and shortcuts only
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\SP-Farms"
  Delete "$DESKTOP\SP-Farms.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SP-Farms"
  DeleteRegKey HKLM "Software\SP-Farms"

  ; Notice: $APPDATA\SP-Farms is preserved by default to protect user databases and backups.
SectionEnd
