VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "Ten_skoroszyt"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Sub NumerujInteger()

    Dim ws As Worksheet
    Dim lastRow As Long
    Dim i As Long
    Dim licznik As Long

    Set ws = ActiveSheet
    licznik = 1

    Application.ScreenUpdating = False

    ' ZnajdŸ ostatni wiersz w kolumnie A
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row

    For i = 1 To lastRow
        If IsNumeric(ws.Cells(i, "A").Value) Then
                ws.Cells(i, "A").Value = licznik
                licznik = licznik + 1
        End If
    Next i

    Application.ScreenUpdating = True

    MsgBox "Numerowanie zakoñczone.", vbInformation

End Sub

