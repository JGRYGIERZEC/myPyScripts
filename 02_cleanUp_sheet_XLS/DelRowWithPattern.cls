VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "Ten_skoroszyt"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Sub UsunWierszeZWzorcemTekstu()

    Dim ws As Worksheet
    Dim lastRow As Long
    Dim i As Long
    Dim txt As String

    Set ws = ActiveSheet

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    For i = lastRow To 1 Step -1
        txt = ws.Cells(i, 1).Value

        If txt <> "" Then
            If InStr(1, txt, "Woj", vbTextCompare) > 0 _
            Or InStr(1, txt, "W³aœci", vbTextCompare) > 0 _
            Or InStr(1, txt, "Wykaz", vbTextCompare) > 0 Then

                ws.Rows(i).Delete
            End If
        End If
    Next i

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

    MsgBox "Usuwanie zakoñczone.", vbInformation

End Sub

