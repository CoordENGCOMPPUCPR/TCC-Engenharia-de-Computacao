defmodule TccWeb.DashboardLive.Show do
  use TccWeb, :live_view
  alias Tcc.Sensors

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(:sensor, nil)
     |> assign(:paginated_values, %{})
     |> assign(:pages, %{})}
  end

  @impl true
  def handle_params(params, _url, socket) do
    device_id = Map.get(params, "device_id")
    sensor_id = Map.get(params, "sensor_id")

    socket = load_sensor_data(socket, device_id, sensor_id, %{})
    {:noreply, socket}
  end

  @impl true
  def handle_event("change_page", %{"unit" => unit_name, "page" => page}, socket) do
    page = String.to_integer(page)
    pages = Map.put(socket.assigns.pages, unit_name, page)

    device_id = socket.assigns.sensor.device_id
    sensor_id = socket.assigns.sensor.id

    socket = load_sensor_data(socket, device_id, sensor_id, pages)
    {:noreply, socket}
  end

  defp load_sensor_data(socket, device_id, sensor_id, pages) do
    case Sensors.get_sensor(device_id, sensor_id) do
      nil ->
        socket
        |> assign(:sensor, nil)
        |> assign(:paginated_values, %{})
        |> assign(:pages, %{})

      sensor ->
        unit_names = Sensors.list_units_for_sensor(sensor.id)

        pages = Map.merge(Map.new(unit_names, &{&1, 1}), pages)

        paginated_values =
          Map.new(unit_names, fn unit_name ->
            current_page = Map.get(pages, unit_name, 1)
            {unit_name, Sensors.paginate_sensor_values(sensor.id, unit_name, current_page, 10)}
          end)

        socket
        |> assign(:sensor, sensor)
        |> assign(:pages, pages)
        |> assign(:paginated_values, paginated_values)
    end
  end
end
