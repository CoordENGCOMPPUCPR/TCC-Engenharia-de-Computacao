defmodule TccWeb.DashboardLive.Index do
  use TccWeb, :live_view
  alias Tcc.Devices

  @impl true
  def mount(_params, _session, socket) do
    devices = Devices.list_devices()

    {:ok,
     socket
     |> assign(:devices, devices)
     |> assign(:is_live, false)
     |> stream(:sensors, [])}
  end

  @impl true
  def handle_params(params, _url, socket) do
    device_id = Map.get(params, "device_id") || default_device_id(socket)

    if connected?(socket) do
      Phoenix.PubSub.subscribe(Tcc.PubSub, "device_readings:#{device_id}")
    end

    case get_device_or_nil(device_id) do
      nil ->
        {:noreply,
         socket
         |> assign(:active_device_id, nil)
         |> assign(:active_device_name, nil)
         |> assign(:active_device_location, nil)
         |> stream(:sensors, [], reset: true)}

      device ->
        {:noreply,
         socket
         |> assign(:active_device_id, device.id)
         |> assign(:active_device_name, device.name)
         |> assign(:active_device_location, device.location)
         |> stream(:sensors, device.sensors, reset: true)}
    end
  end

  @impl true
  def handle_info({:new_readings, %{device: device}}, socket) do
    {:noreply,
     socket
     |> stream(:sensors, device.sensors, reset: true)}
  end

  defp get_device_or_nil(nil), do: nil

  defp get_device_or_nil(id) do
    Devices.get_device_with_sensors!(id)
  rescue
    Ecto.NoResultsError -> nil
  end

  defp default_device_id(socket) do
    case socket.assigns.devices do
      [first | _] -> first.id
      _ -> nil
    end
  end
end
