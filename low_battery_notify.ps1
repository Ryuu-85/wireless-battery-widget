param(
  [string]$DeviceName = "Device",
  [int]$Level = 0,
  [int]$Threshold = 20
)

$title = "Low battery"
$body = "$DeviceName battery is $Level%, threshold is $Threshold%."

try {
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
  [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

  $escapedTitle = [System.Security.SecurityElement]::Escape($title)
  $escapedBody = [System.Security.SecurityElement]::Escape($body)
  $xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$escapedTitle</text>
      <text>$escapedBody</text>
    </binding>
  </visual>
  <audio silent="true" />
</toast>
"@

  $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
  $doc.LoadXml($xml)
  $toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Wireless Battery Widget").Show($toast)
} catch {
  # Keep failures silent. The widget already shows the low battery state.
}
