defmodule Tcc.SensorsTest do
  use Tcc.DataCase

  alias Tcc.Sensors

  describe "sensors" do
    alias Tcc.Sensors.Sensor

    import Tcc.SensorsFixtures

    @invalid_attrs %{module: nil, timestamp: nil, unit: nil, value: nil}

    test "list_sensors/0 returns all sensors" do
      sensor = sensor_fixture()
      assert Sensors.list_sensors() == [sensor]
    end

    test "get_sensor!/1 returns the sensor with given id" do
      sensor = sensor_fixture()
      assert Sensors.get_sensor!(sensor.id) == sensor
    end

    test "create_sensor/1 with valid data creates a sensor" do
      valid_attrs = %{
        module: "some module",
        timestamp: ~U[2026-10-07 02:32:00.000000Z],
        unit: "some unit",
        value: "120.5"
      }

      assert {:ok, %Sensor{} = sensor} = Sensors.create_sensor(valid_attrs)
      assert sensor.module == "some module"
      assert sensor.timestamp == ~U[2026-10-07 02:32:00.000000Z]
      assert sensor.unit == "some unit"
      assert sensor.value == Decimal.new("120.5")
    end

    test "create_sensor/1 with invalid data returns error changeset" do
      assert {:error, %Ecto.Changeset{}} = Sensors.create_sensor(@invalid_attrs)
    end

    test "update_sensor/2 with valid data updates the sensor" do
      sensor = sensor_fixture()

      update_attrs = %{
        module: "some updated module",
        timestamp: ~U[2026-10-08 02:32:00.000000Z],
        unit: "some updated unit",
        value: "456.7"
      }

      assert {:ok, %Sensor{} = sensor} = Sensors.update_sensor(sensor, update_attrs)
      assert sensor.module == "some updated module"
      assert sensor.timestamp == ~U[2026-10-08 02:32:00.000000Z]
      assert sensor.unit == "some updated unit"
      assert sensor.value == Decimal.new("456.7")
    end

    test "update_sensor/2 with invalid data returns error changeset" do
      sensor = sensor_fixture()
      assert {:error, %Ecto.Changeset{}} = Sensors.update_sensor(sensor, @invalid_attrs)
      assert sensor == Sensors.get_sensor!(sensor.id)
    end

    test "delete_sensor/1 deletes the sensor" do
      sensor = sensor_fixture()
      assert {:ok, %Sensor{}} = Sensors.delete_sensor(sensor)
      assert_raise Ecto.NoResultsError, fn -> Sensors.get_sensor!(sensor.id) end
    end

    test "change_sensor/1 returns a sensor changeset" do
      sensor = sensor_fixture()
      assert %Ecto.Changeset{} = Sensors.change_sensor(sensor)
    end
  end
end
