defmodule Tcc.Sensors do
  @moduledoc """
  The Sensors context.
  """

  import Ecto.Query, warn: false

  alias Ecto.Multi
  alias Tcc.Devices
  alias Tcc.Devices.Device
  alias Tcc.Repo
  alias Tcc.Sensors.{Sensor, SensorValue}

  @doc """
  Returns the list of sensors.

  ## Examples

      iex> list_sensors()
      [%Sensor{}, ...]

  """
  def list_sensors do
    Repo.all(Sensor)
  end

  @doc """
  Returns the list of sensors preloaded with their values and units.
  """
  def list_sensors_with_values do
    Sensor
    |> Repo.all()
    |> Repo.preload(values: [:unit])
  end

  def list_units_for_sensor(sensor_id) do
    SensorValue
    |> where([v], v.sensor_id == ^sensor_id)
    |> select([v], v.unit_name)
    |> distinct(true)
    |> Repo.all()
  end

  @doc """
  Gets a single sensor.

  Raises `Ecto.NoResultsError` if the Sensor does not exist.

  ## Examples

      iex> get_sensor!(123)
      %Sensor{}

      iex> get_sensor!(456)
      ** (Ecto.NoResultsError)

  """
  def get_sensor!(id), do: Repo.get!(Sensor, id)

  def get_sensor(device_id, sensor_id) do
    Sensor
    |> where([s], s.device_id == ^device_id and s.id == ^sensor_id)
    |> Repo.one()
    |> Repo.preload([:device])
  end

  def get_sensor_with_values(device_id, sensor_id) do
    Sensor
    |> where([s], s.device_id == ^device_id and s.id == ^sensor_id)
    |> Repo.one()
    |> Repo.preload([:device, values: [:unit]])
  end

  def paginate_sensor_values(sensor_id, unit_name, page \\ 1, per_page \\ 10) do
    offset = (page - 1) * per_page

    base_query =
      SensorValue
      |> where([v], v.sensor_id == ^sensor_id and v.unit_name == ^unit_name)

    total_count = Repo.aggregate(base_query, :count, :timestamp)

    entries =
      base_query
      |> order_by([v], desc: v.timestamp)
      |> limit(^per_page)
      |> offset(^offset)
      |> Repo.all()
      |> Repo.preload(:unit)

    %{
      entries: entries,
      total_count: total_count,
      total_pages: max(1, ceil(total_count / per_page)),
      current_page: page
    }
  end

  @doc """
  Creates a sensor.

  ## Examples

      iex> create_sensor(%{field: value})
      {:ok, %Sensor{}}

      iex> create_sensor(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def create_sensor(attrs) do
    %Sensor{}
    |> Sensor.changeset(attrs)
    |> Repo.insert()
  end

  @doc """
  Updates a sensor.

  ## Examples

      iex> update_sensor(sensor, %{field: new_value})
      {:ok, %Sensor{}}

      iex> update_sensor(sensor, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def update_sensor(%Sensor{} = sensor, attrs) do
    sensor
    |> Sensor.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a sensor.

  ## Examples

      iex> delete_sensor(sensor)
      {:ok, %Sensor{}}

      iex> delete_sensor(sensor)
      {:error, %Ecto.Changeset{}}

  """
  def delete_sensor(%Sensor{} = sensor) do
    Repo.delete(sensor)
  end

  @doc """
  Returns an `%Ecto.Changeset{}` for tracking sensor changes.

  ## Examples

      iex> change_sensor(sensor)
      %Ecto.Changeset{data: %Sensor{}}

  """
  def change_sensor(%Sensor{} = sensor, attrs \\ %{}) do
    Sensor.changeset(sensor, attrs)
  end

  @doc """
  Ingests sensor readings using Ecto.Multi:
  1. Finds or creates the Device by `external_id`.
  2. Finds or creates each Sensor by `external_id` (associated with the device).
  3. Inserts all new SensorValue records via bulk insert.
  """

  def ingest_readings(%{"device" => device_ext_id, "sensors" => sensors_payload}) do
    Multi.new()
    |> Multi.run(:device, fn repo, _changes ->
      {:ok, find_or_create_device(repo, device_ext_id)}
    end)
    |> Multi.run(:sensors, fn repo, %{device: device} ->
      sensors =
        Enum.map(sensors_payload, fn %{"external_id" => sensor_ext_id} = sensor_data ->
          module_name = Map.get(sensor_data, "module", sensor_ext_id)
          sensor = find_or_create_sensor(repo, sensor_ext_id, device.id, module_name)
          {sensor, Map.get(sensor_data, "values", [])}
        end)

      {:ok, sensors}
    end)
    |> Multi.run(:sensor_values, fn repo, %{sensors: sensors_with_values} ->
      now = DateTime.utc_now() |> DateTime.truncate(:second)

      value_records =
        Enum.flat_map(sensors_with_values, fn {sensor, values} ->
          Enum.map(values, fn val ->
            %{
              sensor_id: sensor.id,
              unit_name: val["unit"],
              value: val["value"],
              timestamp: parse_timestamp(val["timestamp"]),
              inserted_at: now,
              updated_at: now
            }
          end)
        end)

      {count, inserted_records} =
        repo.insert_all(SensorValue, value_records,
          on_conflict: :nothing,
          conflict_target: [:sensor_id, :timestamp, :unit_name],
          returning: true
        )

      {:ok, %{count: count, records: inserted_records}}
    end)
    |> Repo.transaction()
    |> case do
      {:ok, %{device: device} = result} ->
        Phoenix.PubSub.broadcast(
          Tcc.PubSub,
          "device_readings:#{device.id}",
          {:new_readings, %{device: Devices.get_device_with_sensors!(device.id)}}
        )

        {:ok, result}

      error ->
        error
    end
  end

  defp find_or_create_device(repo, external_id) do
    case repo.get_by(Device, external_id: external_id) do
      %Device{} = device ->
        device

      nil ->
        %Device{}
        |> Device.changeset(%{
          external_id: external_id,
          name: external_id,
          location: "Auto-provisioned"
        })
        |> repo.insert!()
    end
  end

  defp find_or_create_sensor(repo, external_id, device_id, module_name) do
    case repo.get_by(Sensor, external_id: external_id) do
      %Sensor{} = sensor ->
        sensor

      nil ->
        %Sensor{}
        |> Sensor.changeset(%{
          external_id: external_id,
          module: module_name,
          device_id: device_id
        })
        |> repo.insert!()
    end
  end

  defp parse_timestamp(timestamp) when is_integer(timestamp) do
    case DateTime.from_unix(timestamp) do
      {:ok, dt} -> dt
      _ -> DateTime.utc_now() |> DateTime.truncate(:second)
    end
  end

  defp parse_timestamp(timestamp) when is_binary(timestamp) do
    case DateTime.from_iso8601(timestamp) do
      {:ok, dt, _offset} -> dt
      _ -> DateTime.utc_now() |> DateTime.truncate(:second)
    end
  end

  defp parse_timestamp(_), do: DateTime.utc_now() |> DateTime.truncate(:second)
end
