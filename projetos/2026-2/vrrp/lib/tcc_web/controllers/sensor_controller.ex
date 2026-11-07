defmodule TccWeb.SensorController do
  use TccWeb, :controller
  alias Tcc.Sensors

  def ingest(conn, params) do
    params
    |> Sensors.ingest_readings()
    |> case do
      {:ok, %{device: device, sensor_values: %{count: count}}} ->
        conn
        |> put_status(:created)
        |> json(%{
          status: "ok",
          device_id: device.id,
          records_inserted: count
        })

      {:error, step, reason, _changes_so_far} ->
        conn
        |> put_status(:unprocessable_entity)
        |> json(%{
          error: "Failed to ingest readings",
          step: step,
          details: inspect(reason)
        })
    end
  end
end
